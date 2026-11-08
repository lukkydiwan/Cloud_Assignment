import unittest
import json
import ipaddress
from worker.clean import extract_json, ALLOWED_INTENTS, REQUIRED_KEYS
from tools.nacl_sim import load_rules, decide


class TestCommandParserPipeline(unittest.TestCase):
    """Unit tests validating pipeline components, NACL rules, and cleaning logic."""

    def test_schema_rules_and_keys(self):
        """Test 1: Validate 4-key requirements and allowed intents."""
        valid_sample = {
            "intent": "alarm_set",
            "date": "tomorrow",
            "time": "seven am",
            "place": None,
        }
        self.assertEqual(set(valid_sample.keys()), REQUIRED_KEYS)
        self.assertIn(valid_sample["intent"], ALLOWED_INTENTS)

        invalid_intent_sample = {
            "intent": "play_music",
            "date": None,
            "time": None,
            "place": None,
        }
        self.assertNotIn(invalid_intent_sample["intent"], ALLOWED_INTENTS)

    def test_clean_extract_json(self):
        """Test 2: Test JSON extraction and malformed payload filtering."""
        clean_json_str = '{"intent": "weather_query", "date": null, "time": null, "place": "london"}'
        parsed = extract_json(clean_json_str)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["intent"], "weather_query")

        # Markdown wrapped string
        markdown_str = '```json\n{"intent": "datetime_query", "date": null, "time": null, "place": "tokyo"}\n```'
        parsed_md = extract_json(markdown_str)
        self.assertIsNotNone(parsed_md)
        self.assertEqual(parsed_md["place"], "tokyo")

        # Broken JSON
        broken_str = '{"intent": "alarm_set", "date": "tomorrow", ...'
        self.assertIsNone(extract_json(broken_str))

    def test_nacl_firewall_rules(self):
        """Test 3: Test stateless NACL simulator decisions for public subnet."""
        rules = load_rules("network/nacl.json")

        # Test abusive IP blocked on web port 443
        pkt_abusive = {
            "direction": "inbound",
            "protocol": "tcp",
            "port": 443,
            "address": "198.51.100.25",
        }
        action, rule_num = decide(rules, pkt_abusive)
        self.assertEqual(action, "deny")

        # Test legitimate web traffic allowed
        pkt_web = {
            "direction": "inbound",
            "protocol": "tcp",
            "port": 443,
            "address": "203.0.113.10",
        }
        action_web, rule_web = decide(rules, pkt_web)
        self.assertEqual(action_web, "allow")

        # Test SSH allowed ONLY from management subnet (10.20.5.128/27)
        pkt_ssh_mgmt = {
            "direction": "inbound",
            "protocol": "tcp",
            "port": 22,
            "address": "10.20.5.130",
        }
        action_mgmt, _ = decide(rules, pkt_ssh_mgmt)
        self.assertEqual(action_mgmt, "allow")

        pkt_ssh_external = {
            "direction": "inbound",
            "protocol": "tcp",
            "port": 22,
            "address": "203.0.113.10",
        }
        action_ext, _ = decide(rules, pkt_ssh_external)
        self.assertEqual(action_ext, "deny")


if __name__ == "__main__":
    unittest.main()
