import unittest
import yaml
from config_validation import PublicLoader

class YamlTests(unittest.TestCase):
    def test_secret_reference_does_not_read_file(self):
        self.assertEqual(yaml.load('url: !secret private_url', Loader=PublicLoader), {'url': 'private_url'})
    def test_include_does_not_read_file(self):
        self.assertEqual(yaml.load('items: !include nonexistent.yaml', Loader=PublicLoader), {'items': 'nonexistent.yaml'})
    def test_python_object_tag_refused(self):
        with self.assertRaises(yaml.constructor.ConstructorError):
            yaml.load('!!python/object/apply:os.system [echo fixture]', Loader=PublicLoader)
    def test_blueprint_input_is_parsed_without_resolving(self):
        self.assertEqual(yaml.load('entity: !input source', Loader=PublicLoader), {'entity': 'source'})
    def test_empty_secret_refused(self):
        with self.assertRaises(ValueError):
            yaml.load('item: !secret ""', Loader=PublicLoader)
    def test_malformed_yaml_refused(self):
        with self.assertRaises(yaml.YAMLError):
            yaml.load('item: [', Loader=PublicLoader)



class ComposeInterpolationTests(unittest.TestCase):
    def required(self, text):
        from config_validation import compose_variables
        return compose_variables(yaml.safe_load(text), required=True)

    def test_yaml_comments_are_not_requirements(self):
        self.assertEqual(self.required('services: {} # ${TOKEN:?required}'), set())

    def test_escaped_dollars_are_not_requirements(self):
        self.assertEqual(self.required('command: "$${TOKEN:?required}"'), set())
        self.assertEqual(self.required('command: "$$$${TOKEN:?required}"'), set())

    def test_unescaped_requirement_after_literal_dollar_is_checked(self):
        self.assertEqual(self.required('command: "$$${TOKEN:?required}"'), {'TOKEN'})

    def test_mapping_keys_are_not_interpolated(self):
        self.assertEqual(self.required('labels: {"${TOKEN:?required}": "value"}'), set())

    def test_nested_values_and_list_entries_are_checked(self):
        self.assertEqual(self.required('services: {app: {environment: ["KEY=${TOKEN:?required}"]}}'), {'TOKEN'})

    def test_optional_values_do_not_become_requirements(self):
        self.assertEqual(self.required('command: "${OPTIONAL:-default} ${PLAIN}"'), set())

    def test_non_colon_required_operator_is_checked(self):
        self.assertEqual(self.required('command: "${TOKEN?required}"'), {'TOKEN'})


class ComposeModelTests(unittest.TestCase):
    def test_conditional_requirements_pass_actual_compose(self):
        import tempfile
        from pathlib import Path
        from config_validation import compose
        expressions = (
            '${TOKEN?required}',
            '${PRIMARY:-${BACKUP:?required}}',
            '${PRIMARY-${BACKUP?required}}',
            '${PRIMARY:+${BACKUP:?required}}',
            '${PRIMARY+${BACKUP?required}}',
            '${PRIMARY:-${SECONDARY:-${BACKUP:?required}}}',
            '${PRIMARY:-${PRIMARY:?required}}',
            '${PRIMARY:+${PRIMARY:?required}}',
        )
        for expression in expressions:
            for other in (False, True):
                with self.subTest(expression=expression, other=other), tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / 'compose.yaml'
                    environment = {'VALUE': expression}
                    if other:
                        environment['OTHER'] = '${PRIMARY:?also required}'
                    path.write_text(yaml.safe_dump({'services': {'app': {
                        'image': 'example.invalid/fixture:1', 'environment': environment,
                    }}}))
                    self.assertEqual(compose(path), 1)

    def test_required_operator_probes_distinguish_unset_from_empty(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import config_validation as validation
        for operator, expected in [('?', [None]), (':?', [None, ''])]:
            with self.subTest(operator=operator), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'compose.yaml'
                path.write_text(yaml.safe_dump({'services': {'app': {
                    'image': 'example.invalid/fixture:1',
                    'environment': {'VALUE': '${TOKEN' + operator + 'required}'},
                }}}))
                with patch.object(validation.subprocess, 'run', wraps=validation.subprocess.run) as run:
                    self.assertEqual(validation.compose(path), 1)
                self.assertEqual([call.kwargs['env'].get('TOKEN') for call in run.call_args_list[1:]], expected)

    def test_literals_and_comments_pass_actual_compose(self):
        import tempfile
        from pathlib import Path
        from config_validation import compose
        for value in ('plain', '$${TOKEN:?required}', '$$$${TOKEN:?required}'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'compose.yaml'
                path.write_text('services:\n  app:\n    image: example.invalid/fixture:1\n'
                                '    environment:\n      VALUE: "' + value + '"\n'
                                '# ${COMMENT_ONLY:?required}\n')
                self.assertEqual(compose(path), 1)

    def test_required_input_still_checked_with_actual_compose(self):
        import tempfile
        from pathlib import Path
        from config_validation import compose
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'compose.yaml'
            path.write_text('services:\n  app:\n    image: example.invalid/fixture:1\n'
                            '    environment:\n      VALUE: "${TOKEN:?required}"\n')
            self.assertEqual(compose(path), 1)


if __name__ == '__main__':
    unittest.main()
