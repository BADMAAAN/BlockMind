import json
import unittest
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def schema(self, name):
        return json.loads((ROOT / "protocol/schemas" / f"{name}.schema.json").read_text())

    def test_schemas_are_valid_and_versions_share_identical_wire_format(self):
        for path in (ROOT / "protocol/schemas").glob("*.json"):
            jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text()))
        for version in json.loads((ROOT / "minecraft-mod/targets.json").read_text()):
            jsonschema.validate({"minecraft": version, "adapterVersion": "0.1.1-dev", "protocol": "0.1.0",
                "capabilities": ["OBSERVE_BLOCKS"], "navigation": {"available": False}}, self.schema("hello"))

    def test_orientation_fields_and_priority_controls(self):
        for props in ({"facing": "north", "half": "bottom"}, {"axis": "x"}, {"type": "top"}, {"powered": "false"}):
            jsonschema.validate({"kind": "place_block", "position": {"x": 0, "y": 64, "z": 0},
                "block": "minecraft:oak_stairs", "properties": props}, self.schema("action"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"kind": "place_block", "properties": {"axis": 4}}, self.schema("action"))
        jsonschema.validate({"kind": "emergency_stop"}, self.schema("control"))

    def test_actual_handshake_ack_and_error_envelopes_match_schema(self):
        for kind, payload in (("hello_ack", {"accepted": True}), ("error", {"reason": "protocol mismatch"})):
            jsonschema.validate({"protocol": "0.1.0", "id": "negotiation-1", "type": kind, "payload": payload}, self.schema("envelope"))

    def test_batch_and_execution_configuration_wire_format(self):
        from blockmind.execution import ExecutionConfig
        operation = {"id": "block-1", "position": {"x": 1, "y": 64, "z": 1}, "block": "minecraft:stone", "properties": {}}
        for kind in ("action_batch", "validate_batch"):
            jsonschema.validate({"kind": kind, "operations": [operation]}, self.schema("action"))
        jsonschema.validate({"kind": "configure_execution", **ExecutionConfig().to_dict()}, self.schema("action"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"kind": "action_batch", "operations": [operation]*257}, self.schema("action"))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"kind": "action_batch", "operations": [operation]*33}, self.schema("action"))
