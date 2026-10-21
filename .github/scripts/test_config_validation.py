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

if __name__ == '__main__':
    unittest.main()
