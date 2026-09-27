import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1]/'plugins/card-review-toolkit/skills/card-proofreader/scripts/text_inventory.py'
spec = importlib.util.spec_from_file_location('text_inventory', SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


class TextTests(unittest.TestCase):
    def fixture(self):
        item = {'id': 'code', 'kind': 'text', 'original': 'DPBP#037', 'enhanced': 'DPBP#097',
                'numeric_review': 'different', 'numeric_evidence': 'Synthetic paired footer'}
        r = {'regions': {'footer': {'items': [item]}},
             'text_extraction': {'mode': 'visual', 'ocr_unavailable_reason': 'Test fixture', 'visual_sweep_complete': True, 'evidence': 'Fixture'},
             'numeric_fields': {f: {'absent_in_both': True, 'evidence': 'Fixture'} for f in inventory.FIELDS}}
        r['numeric_fields']['other_footer_codes'] = {'item_ids': ['code'], 'evidence': 'Both corners inspected'}
        return r

    def test_piepi_code_digit_change(self):
        d = inventory.differences('DPBP#037', 'DPBP#097')
        self.assertFalse(d['numbers_equal'])
        self.assertEqual(d['original_numbers'], ['037'])
        self.assertEqual(d['characters'][0]['original'], '3')
        self.assertEqual(d['characters'][0]['enhanced'], '9')

    def test_exact_case_diacritics_punctuation_and_zeros(self):
        for a, b in [('Illus.', 'illus.'), ('Pokémon', 'Pokemon'), ('77/130', '77/180'),
                     ('035', '35'), ('20+', '20'), ('7,5', '7.5'), ('A B', 'A  B')]:
            self.assertFalse(inventory.differences(a, b)['equal'])
        self.assertTrue(inventory.differences('77/130', '77/130')['equal'])

    def test_duplicate_numbers_and_order_preserved(self):
        self.assertEqual(inventory.numbers('20 plus 20'), ['20', '20'])
        self.assertFalse(inventory.differences('20 plus 20', '20')['numbers_equal'])
        self.assertFalse(inventory.differences('10 20', '20 10')['numbers_equal'])

    def test_declared_match_cannot_hide_literal_difference(self):
        r = self.fixture()
        r['regions']['footer']['items'][0]['numeric_review'] = 'checked'
        result = inventory.validate({'key': 'x'}, r, '.')
        self.assertFalse(result['issues'])
        self.assertEqual(len(result['literal_differences']), 1)

    def test_missing_numeric_review_or_category_fails(self):
        r = self.fixture()
        del r['numeric_fields']['other_footer_codes']
        del r['regions']['footer']['items'][0]['numeric_review']
        result = inventory.validate({'key': 'x'}, r, '.')
        self.assertEqual(len(result['issues']), 2)

    def test_uncertain_digits_remain_unresolved(self):
        r = self.fixture()
        r['regions']['footer']['items'][0]['numeric_review'] = 'unresolved'
        self.assertEqual(inventory.validate({'key': 'x'}, r, '.')['unresolved'], ['code'])

    def test_ocr_omission_and_tampering_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'ocr.json'
            m = {'key': 'x', 'artifacts': {'original-aligned.png': 'a', 'enhanced-aligned.png': 'b'}}
            data = {'key': 'x', 'artifact_hashes': m['artifacts'],
                    'passes': ['original:full', 'original:footer', 'enhanced:full', 'enhanced:footer'],
                    'candidates': [{'id': 'original:footer:0', 'text': 'DPBP#037'}]}
            p.write_text(json.dumps(data))
            r = self.fixture()
            r['text_extraction'].update(mode='rapidocr', file='ocr.json', sha256=inventory.sha(p))
            self.assertTrue(inventory.validate(m, r, tmp)['issues'])
            r['text_extraction']['resolutions'] = {'original:footer:0': {'disposition': 'mapped', 'item_ids': ['code'], 'evidence': 'Fixture'}}
            self.assertFalse(inventory.validate(m, r, tmp)['issues'])
            p.write_text('{}')
            self.assertTrue(inventory.validate(m, r, tmp)['issues'])

    def test_identity_must_reference_exact_collector(self):
        r = self.fixture()
        r['identity'] = {'original': {'card_id': '77/130'}}
        self.assertTrue(inventory.validate({'key': 'x'}, r, '.')['issues'])


    def test_zorua_internal_word_change_and_missing_text(self):
        self.assertFalse(inventory.differences('wortkarges', 'vorlarges')['equal'])
        self.assertFalse(inventory.differences('Kind.', '')['equal'])
        self.assertTrue(inventory.differences('wortkarges', 'wortkarges')['equal'])

    def test_protocol_missing_evidence_and_reverse_order(self):
        m = {'regions': [{'id': 'top'}, {'id': 'bottom'}]}
        r = {'regions': {rid: {'items': [], 'inventory_reconciliation': {role: {'status': 'verified', 'item_ids': [], 'evidence': 'Fixture inspected'} for role in ['original','enhanced']}} for rid in ['top','bottom']}, 'reverse_sweep': {'region_ids': ['bottom','top'], 'evidence': 'Fixture'}}
        self.assertFalse(inventory.verify_protocol(m,r)['issues'])
        r['reverse_sweep']['region_ids'].reverse()
        self.assertTrue(inventory.verify_protocol(m,r)['issues'])
        r['reverse_sweep']['region_ids'].reverse()
        del r['regions']['bottom']['inventory_reconciliation']['original']
        self.assertTrue(inventory.verify_protocol(m,r)['issues'])

    def test_protocol_requires_both_readings_and_retains_uncertainty(self):
        m = {'regions': [{'id': 'footer'}]}
        item = {'id':'code','kind':'text','original':'037','enhanced':'037'}
        r = {'regions': {'footer': {'items': [item], 'inventory_reconciliation': {role: {'status':'verified','item_ids':['code'],'evidence':'Fixture'} for role in ['original','enhanced']}}}, 'reverse_sweep': {'region_ids':['footer'],'evidence':'Fixture'}}
        self.assertTrue(inventory.verify_protocol(m,r)['issues'])
        item['readings'] = {role: {'literal':'037','status':'verified','character_pass':True,'evidence':'Fixture'} for role in ['original','enhanced']}
        self.assertFalse(inventory.verify_protocol(m,r)['issues'])
        item['readings']['original']['status']='unresolved'
        self.assertTrue(inventory.verify_protocol(m,r)['unresolved'])
        item['readings']['enhanced']['literal']='097'
        self.assertTrue(inventory.verify_protocol(m,r)['issues'])
        r['regions']['footer']['inventory_reconciliation']['original']['item_ids']=[]
        self.assertTrue(inventory.verify_protocol(m,r)['issues'])


if __name__ == '__main__':
    unittest.main()
