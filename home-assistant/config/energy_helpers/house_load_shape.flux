// Read-only prior30completedBrisbane-day shoulder shape, existing numeric state history.
// HA omits unavailable/unknown from Influx: coverage is reconstructed numeric coverage,
// not proof of historical source availability. Missing anchors are never zero-filled.
import "date"
import "timezone"
option location = timezone.location(name: "Australia/Brisbane")
stop = time(v: "__CUTOFF_UTC__")
begin = date.sub(d: 30d, from: stop)
series = (entity, unit) => {
  source = (a,b) => from(bucket:"homeassistant")
    |> range(start:a, stop:b)
    |> filter(fn:(r)=>r.entity_id==entity and r._field=="value" and r._measurement==unit)
  seed = source(a:date.sub(d:365d,from:begin), b:begin)
    |> last()
    |> group(columns:[])
    |> sort(columns:["_time"])
    |> last()
    |> map(fn:(r)=>({_time:begin,_value:r._value,_start:begin,_stop:stop}))
  events = source(a:begin,b:stop)
    |> map(fn:(r)=>({_time:r._time,_value:r._value,_start:begin,_stop:stop}))
  return union(tables:[seed,events])
    |> group(columns:[])
    |> sort(columns:["_time"])
    |> aggregateWindow(every:1m,fn:last,createEmpty:false,timeSrc:"_start")
    |> aggregateWindow(every:1m,fn:mean,createEmpty:true,timeSrc:"_start")
    |> fill(column:"_value",usePrevious:true)
    |> filter(fn:(r)=>exists r._value)
    |> keep(columns:["_time","_value"])
}
house = series(entity:"energy_house_load_power",unit:"kW")
  |> filter(fn:(r)=>date.hour(t:r._time,location:location)>=6 and date.hour(t:r._time,location:location)<11)
ev = series(entity:"myenergi_my_home_power_charging",unit:"W")
  |> filter(fn:(r)=>date.hour(t:r._time,location:location)>=6 and date.hour(t:r._time,location:location)<11)
join(tables:{house:house,ev:ev},on:["_time"],method:"inner")
  |> map(fn:(r)=>({
    day:date.truncate(t:r._time,unit:1d),
    slot:(date.hour(t:r._time,location:location)*60+date.minute(t:r._time,location:location)-360)/30,
    energy:if r._value_house-r._value_ev/1000.0>0.0 then (r._value_house-r._value_ev/1000.0)/60.0 else 0.0,
    clamped:if r._value_ev/1000.0-r._value_house>0.1 then 1 else 0,
    invalid:if r._value_house<0.0 or r._value_ev<0.0 then 1 else 0}))
  |> group(columns:["day","slot"])
  |> reduce(identity:{energy:0.0,samples:0,clamped:0,invalid:0},fn:(r,accumulator)=>({
    energy:accumulator.energy+r.energy,samples:accumulator.samples+1,clamped:accumulator.clamped+r.clamped,invalid:accumulator.invalid+r.invalid}))
  |> keep(columns:["day","slot","energy","samples","clamped","invalid"])
  |> group(columns:[])
  |> sort(columns:["day","slot"])
  |> yield(name:"shoulder_slots")
