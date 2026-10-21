import asyncio,base64,json,tempfile,pathlib,inspect,datetime,logging
logging.getLogger('homeassistant.loader').setLevel(logging.ERROR)
import yaml
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.helpers import template,trigger
from homeassistant.components.script import config as sc
from homeassistant.components.automation import config as ac
from homeassistant.components.template import config as tc
from homeassistant.components import input_boolean,input_select,input_text
ROOT=pathlib.Path(__file__).resolve().parents[2]
FILES={name:(ROOT/rel).read_text() for name,rel in {'modbus_sungrow.yaml': 'integrations/modbus_sungrow.yaml', 'energy.yaml': 'integrations/energy.yaml', 'energy_battery_recovery.jinja': 'custom_templates/energy_battery_recovery.jinja', 'battery_target_override.yaml': 'integrations/battery_target_override.yaml', 'energy_battery_manual.jinja': 'custom_templates/energy_battery_manual.jinja', 'consumption.yaml': 'dashboards/living/views/2-consumption.yaml', 'energy_battery_authority.jinja': 'custom_templates/energy_battery_authority.jinja'}.items()}
class Loader(yaml.SafeLoader): pass
Loader.add_constructor('!secret',lambda l,n:l.construct_scalar(n))
PACKAGES={k:yaml.load(v,Loader=Loader) for k,v in FILES.items() if k.endswith('.yaml') and k!='consumption.yaml'}
count=0
async def main():
 global count
 with tempfile.TemporaryDirectory(prefix='battery-override-check-') as tmp:
  root=pathlib.Path(tmp);(root/'custom_templates').mkdir()
  for k,v in FILES.items():
   if k.endswith('.jinja'):(root/'custom_templates'/k).write_text(v)
  hass=HomeAssistant(tmp)
  loader.async_setup(hass)
  setup=trigger.async_setup(hass)
  if inspect.isawaitable(setup):await setup
  template.async_setup(hass)
  await template.async_load_custom_templates(hass)
  for k,package in PACKAGES.items():
   for domain,mod in [('input_boolean',input_boolean),('input_select',input_select),('input_text',input_text)]:
    if domain in package: mod.CONFIG_SCHEMA({domain:package[domain]})
   for ident,item in package.get('script',{}).items():
    result=await sc.async_validate_config_item(hass,ident,item)
    assert result is not None,(k,'script',ident)
   for i,item in enumerate(package.get('automation',[])):
    result=await ac.async_validate_config_item(hass,str(i),item)
    assert result is not None,(k,'automation',item.get('id'))
   if 'template' in package:
    for item in package['template']:tc.CONFIG_SECTION_SCHEMA(item)
  view=yaml.load(FILES['consumption.yaml'],Loader=Loader)[0]
  panel=next(c for c in view['cards'] if c.get('view_layout',{}).get('grid-area')=='c1')
  buttons=panel['cards'][1]['cards']
  assert [b['name'] for b in buttons]==['50%','60%','70%','80%','90%','100%','Stop']
  for b,target in zip(buttons[:6],[50,60,70,80,90,100]):
   assert b['tap_action']['service']=='script.sg_charge_battery_to_target' and b['tap_action']['service_data']['target_soc']==str(target)
  assert buttons[-1]['tap_action']['service']=='script.sg_cancel_target_battery_charge'
  assert view['theme']=='living-tablet'
  print('YAML and installed HA schemas: PASS')
  n=datetime.datetime.now(datetime.timezone.utc).timestamp()
  def setstate(e,v):hass.states.async_set(e,str(v))
  fixture_time=datetime.datetime.now(datetime.timezone.utc)
  fixture_peak_start=(fixture_time+datetime.timedelta(hours=10)).strftime('%H:%M:%S')
  fixture_peak_end=(fixture_time+datetime.timedelta(hours=15)).strftime('%H:%M:%S')
  def reset():
   for e,v in {'input_datetime.energy_time_peak_start':fixture_peak_start,'input_datetime.energy_time_peak_end':fixture_peak_end,'sensor.battery_level':'49','sensor.max_soc':'100','sensor.sungrow_device_type_code':'3355',
     'input_boolean.sg_battery_control_armed':'on','input_boolean.sg_battery_stop_pending':'off',
     'input_boolean.energy_disable_automation':'off','input_boolean.energy_allow_overnight_battery_charge':'off',
     'input_boolean.sg_battery_target_preparing':'off','input_text.energy_battery_charge_session':'',
     'input_text.sg_battery_manual_lease':'','input_text.sg_battery_command_ack':'',
     'input_text.energy_battery_recovery':'','input_text.sg_battery_normal_confirmation':'',
     'input_text.sg_battery_authority_epoch':'test-epoch','script.sg_battery_command_owner':'off',
     'script.sg_battery_request':'off','sensor.ems_mode_selection_raw':'2',
     'sensor.battery_forced_charge_discharge_cmd_raw':'170','sensor.battery_forced_charge_discharge_power':'10000',
     'sensor.battery_power_raw':'3000','binary_sensor.energy_state_battery_should_be_charging':'off'}.items():setstate(e,v)
  def render(s,variables=None):return template.Template(s,hass).async_render(variables or {})
  def check(s,expected,label,variables=None):
   global count
   result=render(s,variables);assert result==expected,(label,result,expected);count+=1
  policy="{% from 'energy_battery_manual.jinja' import battery_manual_permitted %}{% set p=battery_manual_permitted|as_function %}{{ p(lease) }}"
  active="{% from 'energy_battery_manual.jinja' import battery_target_override_active %}{% set p=battery_target_override_active|as_function %}{{ p() }}"
  target=dict(id='target-test',start=int(n)-180,end=int(n)+28800-180,op='charge',power=10000,done=False,kind='target',target=80,rearm=False)
  legacy=dict(id='manual-test',start=int(n)-180,end=int(n)+720,op='charge',power=3000,done=False)
  reset()
  check(policy,True,'target bypasses overnight permission',{'lease':target})
  limit="{% from 'energy_battery_manual.jinja' import battery_request_power_limit %}{% set p=battery_request_power_limit|as_function %}{{ p(source,op,ident) }}"
  setstate('input_text.sg_battery_manual_lease',json.dumps(target))
  check(limit,10000,'target maximum',{'source':'manual','op':'charge','ident':target['id']})
  for source,op,ident in [('session','charge',target['id']),('manual','discharge',target['id']),('manual','charge','other'),('','charge',target['id']),('manual','stage',target['id'])]:
   check(limit,3000,'non-target ceiling',{'source':source,'op':op,'ident':ident})
  setstate('sensor.sungrow_device_type_code','3354');check(policy,False,'different model rejected',{'lease':target})
  check(limit,3000,'different model cannot elevate ceiling',{'source':'manual','op':'charge','ident':target['id']})
  reset()
  check(policy,False,'legacy cannot request target maximum',{'lease':dict(legacy,power=10000)})

  for pct in [50,60,70,80,90,100]:check(policy,True,'allowed target '+str(pct),{'lease':dict(target,target=pct)})
  for pct in [0,40,55,101,'80',None]:check(policy,False,'invalid target '+str(pct),{'lease':dict(target,target=pct)})
  for field,value in [('power',10001),('power',3000),('power',2999),('done',True),('op','discharge'),('end',int(n)+28801),('start',int(n)+3600)]:check(policy,False,'invalid '+field,{'lease':dict(target,**{field:value})})
  check(policy,False,'legacy charge still requires permission',{'lease':legacy})
  setstate('input_boolean.energy_allow_overnight_battery_charge','on');check(policy,True,'legacy permitted',{'lease':legacy})
  setstate('sensor.battery_level','90');check(policy,False,'legacy ceiling remains 90',{'lease':legacy})
  check(policy,True,'100 target admitted above 90',{'lease':dict(target,target=100)})
  setstate('sensor.battery_level','100');check(policy,False,'target reached',{'lease':dict(target,target=100)})
  for entity,value in [('sensor.battery_level','unavailable'),('sensor.max_soc','unavailable'),('input_boolean.sg_battery_control_armed','off'),('input_boolean.sg_battery_stop_pending','on'),('input_boolean.energy_disable_automation','on')]:
   reset();setstate(entity,value);check(policy,False,'reject '+entity,{'lease':target})
  reset();setstate('sensor.max_soc','90');check(policy,False,'respect inverter SOC maximum',{'lease':dict(target,target=100)})
  reset();check(active,False,'idle switch off')
  setstate('input_boolean.sg_battery_target_preparing','on');check(active,True,'preparing switch on')
  setstate('input_boolean.sg_battery_target_preparing','off');setstate('input_text.sg_battery_manual_lease',json.dumps(target));check(active,True,'charging switch on')
  setstate('input_text.sg_battery_manual_lease',json.dumps(dict(target,done=True,stop_requested=True)));check(active,True,'unverified Stop switch remains on')
  setstate('input_text.sg_battery_manual_lease',json.dumps(dict(target,done=True,finished=True)));check(active,False,'verified completion switch off')
  # Exercise all five actual admission barriers (ingress, owner and pre-write rechecks).
  def strings(obj):
   if isinstance(obj,dict):
    for v in obj.values():yield from strings(v)
   elif isinstance(obj,list):
    for v in obj:yield from strings(v)
   elif isinstance(obj,str):yield obj
  barriers=[s for s in strings(PACKAGES['modbus_sungrow.yaml']['script']) if 'manual_permitted(lease)' in s]
  assert len(barriers)==5
  reset();setstate('sensor.battery_level','95');setstate('input_text.sg_battery_manual_lease',json.dumps(dict(target,target=100)))
  variables={'op':'charge','source':'manual','requested_w':10000,'request_id':target['id'],'captured_epoch':'test-epoch'}
  for i,b in enumerate(barriers):check(b,False,'valid override admission barrier '+str(i),variables)
  setstate('sensor.battery_level','100')
  for i,b in enumerate(barriers):check(b,True,'completed target admission barrier '+str(i),variables)
  # Actual reconciliation with matching acknowledgement; no writes or services are executed.
  recovery="{% from 'energy_battery_recovery.jinja' import battery_recovery_decision %}{% set p=battery_recovery_decision|as_function %}{{ p() }}"
  reset();setstate('sensor.battery_level','95');setstate('sensor.battery_power_raw','20')
  lease=dict(target,target=100);setstate('input_text.sg_battery_manual_lease',json.dumps(lease))
  ack=dict(id=lease['id'],authority='manual',op='charge',power=10000,epoch='test-epoch',attempt=1,status='confirmed',started=n-170,ts=n-10)
  setstate('input_text.sg_battery_command_ack',json.dumps(ack))
  d=render(recovery);assert d['reason']=='manual_confirmed' and d['action']=='none',d;count+=1
  setstate('sensor.battery_level','90');d=render(recovery);assert d['cancel_manual'] and d['action']=='stop',d;count+=1
  setstate('sensor.battery_level','100');d=render(recovery);assert d['cancel_manual'] and d['action']=='stop',d;count+=1
  reset();setstate('input_text.sg_battery_manual_lease',json.dumps(dict(target,end=int(n)-1)));d=render(recovery);assert d['cancel_manual'] and d['action']=='stop',d;count+=1
  reset();setstate('input_text.sg_battery_manual_lease',json.dumps(target));setstate('sensor.battery_level','unavailable');d=render(recovery);assert d['cancel_manual'] and d['action']=='stop',d;count+=1
  # Confirmed target commands are refreshed at 60s, without closing the lease.
  refresh_policy="{% from 'energy_battery_manual.jinja' import battery_target_refresh_permitted %}{% set p=battery_target_refresh_permitted|as_function %}{{ p(epoch,ident,power) }}"
  reset();setstate('sensor.battery_level','70');setstate('sensor.battery_power_raw','9970')
  keep_lease=dict(target,target=100);setstate('input_text.sg_battery_manual_lease',json.dumps(keep_lease))
  keep_ack=dict(id=keep_lease['id'],authority='manual',op='charge',power=10000,epoch='test-epoch',attempt=1,status='confirmed',started=n-170,ts=n-65)
  setstate('input_text.sg_battery_command_ack',json.dumps(keep_ack))
  args={'epoch':'test-epoch','ident':keep_lease['id'],'power':10000}
  check(refresh_policy,True,'authorized refresh',args)
  d=render(recovery);assert d['action']=='refresh' and d['reason']=='target_keepalive_due' and not d['cancel_manual'],d;count+=1
  setstate('sensor.ems_mode_selection_raw','4');d=render(recovery);assert d['action']=='refresh' and d['reason']=='target_mode_drift' and not d['cancel_manual'],d;count+=1
  setstate('sensor.battery_forced_charge_discharge_power','10600');check(refresh_policy,True,'known cloud power drift can be restored',args)
  setstate('script.sg_battery_command_owner','on');setstate('input_text.sg_battery_control_result','Refreshing: target charge at 10000 W')
  d=render(recovery);assert d['action']=='none' and d['reason']=='manual_refreshing' and not d['cancel_manual'],d;count+=1
  setstate('script.sg_battery_command_owner','off')
  for entity,value in [('sensor.ems_mode_selection_raw','8'),('sensor.ems_mode_selection_raw','2.5'),('sensor.battery_forced_charge_discharge_cmd_raw','187'),('sensor.battery_forced_charge_discharge_power','20000'),('sensor.battery_power_raw','unavailable'),('input_boolean.sg_battery_stop_pending','on'),('input_boolean.energy_disable_automation','on'),('sensor.battery_level','100')]:
   reset();setstate('sensor.battery_level','70');setstate('input_text.sg_battery_manual_lease',json.dumps(keep_lease));setstate('input_text.sg_battery_command_ack',json.dumps(keep_ack));setstate(entity,value)
   check(refresh_policy,False,'refresh blocked: '+entity,args)
   d=render(recovery);assert d['action']=='stop' and d['cancel_manual'],(entity,d);count+=1
  reset();setstate('input_text.sg_battery_manual_lease',json.dumps(keep_lease));setstate('input_text.sg_battery_command_ack',json.dumps(keep_ack))
  for epoch,ident,power in [('old-epoch',keep_lease['id'],10000),('test-epoch','old-id',10000),('test-epoch',keep_lease['id'],3000)]:check(refresh_policy,False,'refresh identity mismatch',{'epoch':epoch,'ident':ident,'power':power})
  setstate('input_text.sg_battery_manual_lease',json.dumps(dict(keep_lease,done=True)));check(refresh_policy,False,'cancelled lease cannot refresh',args)
  print('Refresh/expiry/authority predicates: PASS')

  # Completion predicate: target must stay ON until a correlated fresh Stop is verified.
  section=PACKAGES['battery_target_override.yaml']['script']['sg_reconcile_target_battery_charge']['sequence'][-1]['else']
  stop_pred=section[0]['variables']['stop_verified']
  reset();setstate('sensor.ems_mode_selection_raw','0');setstate('sensor.battery_forced_charge_discharge_cmd_raw','204')
  stopped=dict(target,done=True,stop_at=n-2)
  receipt=dict(status='confirmed',operation='normal',ems=0,command=204,epoch='test-epoch',confirmed_at=n-1)
  setstate('input_text.sg_battery_normal_confirmation',json.dumps(receipt))
  check(stop_pred,True,'completion verified',{'lease':stopped,'stamp':datetime.datetime.now(datetime.timezone.utc).timestamp()})
  for changed in [dict(receipt,epoch='old'),dict(receipt,confirmed_at=n-3),dict(receipt,status='failed')]:
   setstate('input_text.sg_battery_normal_confirmation',json.dumps(changed));check(stop_pred,False,'unverified completion blocked',{'lease':stopped,'stamp':datetime.datetime.now(datetime.timezone.utc).timestamp()})
  sample=dict(target,done=True,stop_requested=True,stop_at=int(n),finished=True)
  assert len(json.dumps(sample,separators=(',',':')))<=255
  yaml.safe_load(FILES['consumption.yaml'])
  tariff="{% from 'energy_battery_manual.jinja' import battery_manual_charge_tariff_permitted %}{% set allowed=battery_manual_charge_tariff_permitted|as_function %}{{ allowed(at) }}"
  setstate('input_datetime.energy_time_peak_start','16:00:00');setstate('input_datetime.energy_time_peak_end','21:00:00')
  for when,want in [('15:59:59',True),('16:00:00',False),('20:59:59',False),('21:00:00',True)]:
   check(tariff,want,'peak cutoff '+when,{'at':datetime.datetime.fromisoformat('2026-10-13T'+when)})
  setstate('input_datetime.energy_time_peak_start','23:00:00');setstate('input_datetime.energy_time_peak_end','06:00:00')
  for when,want in [('22:59:59',True),('23:00:00',False),('05:59:59',False),('06:00:00',True)]:
   check(tariff,want,'overnight peak '+when,{'at':datetime.datetime.fromisoformat('2026-10-13T'+when)})
  for value in ['unknown','unavailable','bad']:
   setstate('input_datetime.energy_time_peak_start',value);check(tariff,False,'bad tariff helper',{'at':datetime.datetime.fromisoformat('2026-10-13T15:00:00')})
  setstate('input_datetime.energy_time_peak_start','16:00:00');setstate('input_datetime.energy_time_peak_end','16:00:00');check(tariff,False,'ambiguous equal tariff helpers',{'at':datetime.datetime.fromisoformat('2026-10-13T15:00:00')})
  reset()
  print('Behaviour cases:',count,'PASS; maximum lease record length:',len(json.dumps(sample,separators=(',',':'))))
  # Run the actual override scripts with inert helper services and a mocked command owner.
  from homeassistant.setup import async_setup_component
  from homeassistant.config_entries import ConfigEntries
  from homeassistant.helpers import entity_registry,device_registry,area_registry,floor_registry,label_registry
  hass.config_entries=ConfigEntries(hass,{})
  device_registry.async_setup(hass)
  for registry in [floor_registry,area_registry,label_registry,device_registry,entity_registry]:
   await registry.async_get(hass).async_load()
  override=PACKAGES['battery_target_override.yaml']
  base=PACKAGES['modbus_sungrow.yaml']
  for entity in hass.states.async_all():
   if entity.entity_id.startswith(('input_boolean.','input_select.','input_text.','script.')):hass.states.async_remove(entity.entity_id)
  bool_cfg={**{k:base['input_boolean'][k] for k in ['sg_battery_control_armed','sg_battery_stop_pending']},**override['input_boolean']}
  bool_cfg['energy_disable_automation']={'initial':False}
  bool_cfg['energy_allow_overnight_battery_charge']={'initial':False}
  texts={**base['input_text'],**override['input_text']}
  texts['energy_battery_charge_session']={'max':255,'initial':''}
  for domain,cfg in [('input_boolean',bool_cfg),('input_select',override['input_select']),('input_text',texts)]:
   assert await async_setup_component(hass,domain,{domain:cfg}),domain
   await hass.async_block_till_done()
  calls=[]
  async def fake_owner(call):
   data=call.data;calls.append(dict(data));stamp=datetime.datetime.now(datetime.timezone.utc).timestamp()
   if data['operation']=='normal':
    lease=json.loads(hass.states.get('input_text.sg_battery_manual_lease').state or '{}')
    if lease.get('done')==False:
     lease.update(done=True,stop_requested=True,stop_at=int(stamp));await hass.services.async_call('input_text','set_value',{'entity_id':'input_text.sg_battery_manual_lease','value':json.dumps(lease,separators=(',',':'))},blocking=True)
    await hass.services.async_call('input_boolean','turn_off',{'entity_id':['input_boolean.sg_battery_control_armed','input_boolean.sg_battery_stop_pending']},blocking=True)
    setstate('sensor.ems_mode_selection_raw','0');setstate('sensor.battery_forced_charge_discharge_cmd_raw','204')
    receipt=dict(status='confirmed',operation='normal',ems=0,command=204,epoch='test-epoch',confirmed_at=stamp)
    await hass.services.async_call('input_text','set_value',{'entity_id':'input_text.sg_battery_normal_confirmation','value':json.dumps(receipt,separators=(',',':'))},blocking=True)
   elif data['operation']=='charge':
    setstate('sensor.ems_mode_selection_raw','2');setstate('sensor.battery_forced_charge_discharge_cmd_raw','170')
    ack=dict(id=data['session_id'],authority=data['authority'],op='charge',power=data['power_w'],epoch=data['authority_epoch'],attempt=1,status='confirmed',started=stamp,ts=stamp)
    await hass.services.async_call('input_text','set_value',{'entity_id':'input_text.sg_battery_command_ack','value':json.dumps(ack,separators=(',',':'))},blocking=True)
  hass.services.async_register('script','sg_battery_request',fake_owner)
  scripts=dict(override['script'])
  scripts['sg_set_self_consumption_mode']=base['script']['sg_set_self_consumption_mode']
  scripts['sg_set_forced_charge_battery_mode']=base['script']['sg_set_forced_charge_battery_mode']
  async def fake_reconcile(call):calls.append({'operation':'automatic_reconcile'})
  hass.services.async_register('script','energy_battery_reconcile',fake_reconcile)
  assert await async_setup_component(hass,'script',{'script':scripts})
  await hass.async_block_till_done()
  assert await async_setup_component(hass,'template',{'template':override['template']})
  await hass.async_block_till_done()
  assert hass.states.get('switch.sg_battery_charge_now') is not None
  await hass.async_start()
  await hass.async_block_till_done()
  async def invoke(name,data=None):await hass.services.async_call('script',name,data or {},blocking=True)
  async def drain():await hass.async_block_till_done()
  async def helper(domain,name,data):await hass.services.async_call(domain,name,data,blocking=True)
  await helper('input_text','set_value',{'entity_id':'input_text.sg_battery_authority_epoch','value':'test-epoch'})
  setstate('input_datetime.energy_time_peak_start',fixture_peak_start);setstate('input_datetime.energy_time_peak_end',fixture_peak_end)
  setstate('script.sg_battery_command_owner','off');setstate('sensor.battery_level','49');setstate('sensor.max_soc','100');setstate('sensor.sungrow_device_type_code','3355')
  await helper('input_select','select_option',{'entity_id':'input_select.sg_battery_charge_target','option':'80'})
  await helper('switch','turn_on',{'entity_id':'switch.sg_battery_charge_now'});await drain()
  active_lease=json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)
  assert active_lease['target']==80 and active_lease['done']==False and active_lease['power']==10000
  assert active_lease['end']-active_lease['start']==28800
  assert hass.states.get('switch.sg_battery_charge_now').state=='on',hass.states.get('switch.sg_battery_charge_now')
  assert [c['operation'] for c in calls]==['normal','charge'],calls
  await invoke('sg_reconcile_target_battery_charge');await drain()
  assert hass.states.get('input_text.sg_battery_target_charge_status').state=='Charging to 80%'
  before=len(calls);await invoke('sg_set_self_consumption_mode');await invoke('sg_set_forced_charge_battery_mode');assert len(calls)==before,'Node-RED compatibility call interfered'
  await helper('input_select','select_option',{'entity_id':'input_select.sg_battery_charge_target','option':'100'})
  assert json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)['target']==80,'Selector mutated captured target'
  setstate('sensor.battery_level','80');await invoke('sg_reconcile_target_battery_charge');await drain()
  stopping=json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)
  assert stopping['done'] and not stopping.get('finished',False)
  await invoke('sg_reconcile_target_battery_charge');await drain()
  completed=json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)
  assert completed['finished'] and render(active)==False
  assert hass.states.get('switch.sg_battery_charge_now').state=='off'
  assert hass.states.get('input_text.sg_battery_target_charge_status').state=='Target reached (80%)'
  # A separate user cancellation follows the same verified-stop completion path.
  setstate('sensor.battery_level','80');await helper('switch','turn_on',{'entity_id':'switch.sg_battery_charge_now'});await drain()
  assert json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)['target']==100
  await helper('switch','turn_off',{'entity_id':'switch.sg_battery_charge_now'});await drain();await invoke('sg_reconcile_target_battery_charge');await drain()
  assert render(active)==False and hass.states.get('input_text.sg_battery_target_charge_status').state=='Cancelled'
  # Already-reached target neither arms nor sends a command.
  before=len(calls);await invoke('sg_start_target_battery_charge',{'target_soc':'50'});assert len(calls)==before
  print('Actual script lifecycle: PASS (start, captured target, Node-RED guards, target completion, cancel, already reached)')

  # Actual button service: select + start, same-target idempotency, retarget, and Stop during retarget.
  # Finish the fake owner's normal receipt through the real lifecycle reconciler when requested.
  real_fake_owner=fake_owner;finish_handover=False
  async def button_owner(call):
   await real_fake_owner(call)
   if finish_handover and call.data['operation']=='normal':await invoke('sg_reconcile_target_battery_charge')
  hass.services.async_register('script','sg_battery_request',button_owner)
  setstate('sensor.battery_level','40')
  await invoke('sg_charge_battery_to_target',{'target_soc':'80'});await drain()
  assert hass.states.get('input_select.sg_battery_charge_target').state=='80'
  assert json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)['target']==80
  before=len(calls);await invoke('sg_charge_battery_to_target',{'target_soc':'80'});assert len(calls)==before,'Same target replayed charging'
  finish_handover=True;before=len(calls)
  await invoke('sg_charge_battery_to_target',{'target_soc':'90'});await drain()
  assert hass.states.get('input_select.sg_battery_charge_target').state=='90'
  assert json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)['target']==90
  assert [c['operation'] for c in calls[before:]]==['normal','normal','charge'],calls[before:]
  finish_handover=False;before=len(calls)
  retarget_task=hass.async_create_task(invoke('sg_charge_battery_to_target',{'target_soc':'100'}))
  for _ in range(100):
   await asyncio.sleep(.01)
   if json.loads(hass.states.get('input_text.sg_battery_manual_lease').state).get('done') and hass.states.get('script.sg_charge_battery_to_target').state=='on':break
  assert hass.states.get('script.sg_charge_battery_to_target').state=='on'
  await invoke('sg_cancel_target_battery_charge')
  await asyncio.gather(retarget_task,return_exceptions=True)
  await invoke('sg_reconcile_target_battery_charge');await drain()
  assert not any(c.get('operation')=='charge' for c in calls[before:]),'Stop tap let pending retarget charge later'
  assert hass.states.get('script.sg_charge_battery_to_target').state=='off'
  assert render(active)==False
  selector_before=hass.states.get('input_select.sg_battery_charge_target').state;before=len(calls)
  await invoke('sg_charge_battery_to_target',{'target_soc':'55'})
  assert len(calls)==before and hass.states.get('input_select.sg_battery_charge_target').state==selector_before,'Invalid target mutated controls'
  setstate('sensor.battery_level','95');before=len(calls)
  await invoke('sg_charge_battery_to_target',{'target_soc':'90'})
  assert hass.states.get('input_select.sg_battery_charge_target').state=='90' and len(calls)==before,'Reached target sent a physical command'
  # The UI indicator follows fresh confirmed forced-mode telemetry.
  forced=override['template'][0]['binary_sensor'][0]
  for mode,command,want in [(2,170,True),(4,170,True),(0,170,False),(2,204,False),(4,187,False)]:
   setstate('sensor.ems_mode_selection_raw',str(mode));setstate('sensor.battery_forced_charge_discharge_cmd_raw',str(command))
   assert render(forced['availability'])==True
   assert render(forced['state'])==want,(mode,command)
  setstate('sensor.ems_mode_selection_raw','unavailable');assert render(forced['availability'])==False
  old=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=181)
  setstate('sensor.ems_mode_selection_raw','2');setstate('sensor.battery_forced_charge_discharge_cmd_raw','170')
  hass.states.get('sensor.ems_mode_selection_raw').last_reported=old
  assert render(forced['availability'])==False
  setstate('sensor.ems_mode_selection_raw','0');setstate('sensor.battery_forced_charge_discharge_cmd_raw','204')
  # Run the actual peak-cutoff action with the inert command owner.
  setstate('sensor.battery_level','49')
  await invoke('sg_charge_battery_to_target',{'target_soc':'80'});await drain()
  assert hass.states.get('switch.sg_battery_charge_now').state=='on'
  utcnow=datetime.datetime.now(datetime.timezone.utc)
  setstate('input_datetime.energy_time_peak_start',(utcnow-datetime.timedelta(hours=1)).strftime('%H:%M:%S'))
  setstate('input_datetime.energy_time_peak_end',(utcnow+datetime.timedelta(hours=1)).strftime('%H:%M:%S'))
  from homeassistant.helpers.script import Script
  cutoff=next(a for a in override['automation'] if a['id']=='sg_forced_charge_peak_cutoff')
  assert render(cutoff['conditions'][0]['value_template'])==True
  cutoff_cfg=await sc.async_validate_config_item(hass,'test_peak_cutoff',{'sequence':cutoff['actions']})
  cutoff_action=Script(hass,cutoff_cfg['sequence'],'Test actual cutoff','script')
  from homeassistant.core import Context
  before=len(calls);await cutoff_action.async_run(context=Context());await drain()
  await invoke('sg_reconcile_target_battery_charge');await drain()
  assert any(c.get('operation')=='normal' for c in calls[before:])
  assert not any(c.get('operation')=='charge' for c in calls[before:])
  assert hass.states.get('switch.sg_battery_charge_now').state=='off'
  before=len(calls);lease_before=hass.states.get('input_text.sg_battery_manual_lease').state
  await invoke('sg_charge_battery_to_target',{'target_soc':'100'});await drain()
  assert hass.states.get('input_text.sg_battery_target_charge_status').state=='Cannot start; peak tariff or tariff helpers unavailable'
  assert len(calls)==before and hass.states.get('input_text.sg_battery_manual_lease').state==lease_before
  assert hass.states.get('switch.sg_battery_charge_now').state=='off'
  setstate('input_datetime.energy_time_peak_start',fixture_peak_start);setstate('input_datetime.energy_time_peak_end',fixture_peak_end)
  print('Charging indicator, actual peak cutoff and blocked peak start: PASS')
  print('Target button service: PASS (selector, start, same target, retarget, Stop race, invalid/reached target)')

  # Execute the real ingress and real owner refresh branch against inert register services.
  from homeassistant.helpers.script import Script
  owner_config=await sc.async_validate_config_item(hass,'test_actual_owner',base['script']['sg_battery_command_owner'])
  ingress_config=await sc.async_validate_config_item(hass,'test_actual_ingress',base['script']['sg_battery_request'])
  owner=Script(hass,owner_config['sequence'],'Test actual owner','script',script_mode='single')
  ingress=Script(hass,ingress_config['sequence'],'Test actual ingress','script',script_mode='queued')
  stage_reads=0;delay_stage=False
  writes=[];device={13049:4,13050:170,13051:10600};cancel_at=None;disable_at=None
  async def register_write(call):
   nonlocal cancel_at,disable_at
   if delay_stage and call.data['address']==13050 and call.data['value']==170:assert stage_reads>=2,'Charge enabled before delayed power readback verified'
   writes.append((call.data['address'],call.data['value']));device[call.data['address']]=call.data['value']
   if cancel_at==len(writes):
    lease=json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)
    lease.update(done=True,stop_requested=True,stop_at=int(datetime.datetime.now(datetime.timezone.utc).timestamp()))
    await helper('input_text','set_value',{'entity_id':'input_text.sg_battery_manual_lease','value':json.dumps(lease,separators=(',',':'))})
   if disable_at==len(writes):await helper('input_boolean','turn_on',{'entity_id':'input_boolean.energy_disable_automation'})
  async def update_registers(call):
   nonlocal stage_reads
   stale=False
   if delay_stage and device[13049]==0 and device[13050]==204 and device[13051]==10000:
    stage_reads+=1;stale=stage_reads==1
   setstate('sensor.battery_level','70')
   for addr,entity in [(13049,'sensor.ems_mode_selection_raw'),(13050,'sensor.battery_forced_charge_discharge_cmd_raw'),(13051,'sensor.battery_forced_charge_discharge_power')]:setstate(entity,10600 if stale and addr==13051 else device[addr])
  async def real_owner(call):
   setstate('script.sg_battery_command_owner','on')
   try:await owner.async_run(dict(call.data),context=call.context)
   finally:setstate('script.sg_battery_command_owner','off')
  async def real_ingress(call):
   setstate('script.sg_battery_request','on')
   try:await ingress.async_run(dict(call.data),context=call.context)
   finally:setstate('script.sg_battery_request','off')
  hass.services.async_register('modbus','write_register',register_write)
  hass.services.async_register('homeassistant','update_entity',update_registers)
  from homeassistant.core import ServiceCall
  async def dispatch_owner(call):
   assert call.data['entity_id'] in ('script.sg_battery_command_owner',['script.sg_battery_command_owner'])
   hass.async_create_task(real_owner(ServiceCall(hass,'script','sg_battery_command_owner',call.data['variables'],context=call.context)))
  hass.services.async_register('script','turn_on',dispatch_owner)
  hass.services.async_register('script','sg_battery_command_owner',real_owner)
  hass.services.async_register('script','sg_battery_request',real_ingress)
  async def ready():
   reset();setstate('sensor.battery_level','70');setstate('sensor.ems_mode_selection_raw','4');setstate('sensor.battery_forced_charge_discharge_power','10600');setstate('sensor.battery_power_raw','9970')
   await helper('input_boolean','turn_on',{'entity_id':'input_boolean.sg_battery_control_armed'})
   await helper('input_boolean','turn_off',{'entity_id':['input_boolean.sg_battery_stop_pending','input_boolean.energy_disable_automation']})
   await helper('input_text','set_value',{'entity_id':'input_text.sg_battery_authority_epoch','value':'test-epoch'})
   await helper('input_text','set_value',{'entity_id':'input_text.sg_battery_manual_lease','value':json.dumps(keep_lease,separators=(',',':'))})
   await helper('input_text','set_value',{'entity_id':'input_text.sg_battery_command_ack','value':json.dumps(keep_ack,separators=(',',':'))})
  await ready();lease_before=hass.states.get('input_text.sg_battery_manual_lease').state
  refresh_request={'operation':'refresh','authority':'manual','session_id':keep_lease['id'],'authority_epoch':'test-epoch','power_w':10000}
  await invoke('sg_battery_request',refresh_request);await drain()
  assert writes==[(13051,10000),(13050,170),(13049,2)],writes
  assert hass.states.get('input_text.sg_battery_manual_lease').state==lease_before,'Refresh changed target/deadline/identity'
  refreshed=json.loads(hass.states.get('input_text.sg_battery_command_ack').state)
  assert refreshed['status']=='confirmed' and refreshed['started']==keep_ack['started'] and refreshed['ts']>keep_ack['ts'],refreshed
  assert hass.states.get('input_text.sg_battery_control_result').state.startswith('Confirmed: target charge refreshed')
  assert render(active)==True and hass.states.get('switch.sg_battery_charge_now').state=='on'
  # Cancellation or global-disable between writes prevents any later enable write.
  writes.clear();cancel_at=1;await ready();await invoke('sg_battery_request',refresh_request);await drain()
  assert writes==[(13051,10000)] and json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)['done'],writes
  cancel_at=None;disable_at=1;writes.clear();await ready();await invoke('sg_battery_request',refresh_request);await drain();assert writes==[(13051,10000)],writes
  disable_at=None;writes.clear();await ready();await invoke('sg_battery_request',dict(refresh_request,authority_epoch='old-epoch'));assert writes==[],writes
  print('Real ingress/owner refresh and cancellation races: PASS')

  # The inverter can return its previous setpoint once after a successful write.
  # Execute the real initial start and prohibit charge enable before exact fresh staging.
  writes.clear();device.update({13049:0,13050:204,13051:10600});await ready()
  await helper('input_text','set_value',{'entity_id':'input_text.sg_battery_command_ack','value':''})
  for name in ['sg_battery_last_command_session','sg_battery_last_command_attempt','sg_battery_owner_started_session','sg_battery_owner_started_attempt']:
   await helper('input_text','set_value',{'entity_id':'input_text.'+name,'value':''})
  delay_stage=True
  await invoke('sg_battery_request',dict(refresh_request,operation='charge',attempt=1));await drain()
  started=json.loads(hass.states.get('input_text.sg_battery_command_ack').state)
  assert started['status']=='confirmed' and started['started'] is not None,started
  assert stage_reads>=2 and writes.count((13050,170))==1,writes
  assert device=={13049:2,13050:170,13051:10000},device
  assert not json.loads(hass.states.get('input_text.sg_battery_manual_lease').state)['done']
  print('Real initial start with delayed inverter setpoint readback: PASS')

  await hass.async_stop()
asyncio.run(main())
