"""Local OCR candidates and exact comparison; neither certifies visual accuracy."""
import argparse
import difflib
import hashlib
import importlib.metadata
import json
import re
import time
import unicodedata
from pathlib import Path

FIELDS = ('collector_number', 'other_footer_codes', 'copyright_year',
          'hp_level', 'species_measurements', 'attack_numbers', 'weakness_resistance')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def numbers(text):
    # Strings, never int/float: retain leading zeros, signs and separators.
    return re.findall(r'[+âˆ’-]?\d+(?:[.,/]\d+)*(?:[+Ã—x%])?', text)


def punctuation(text):
    """Literal punctuation, not OCR-derived proof of the printed mark's shape."""
    return [{'index': i, 'character': c, 'codepoint': f'U+{ord(c):04X}',
             'name': unicodedata.name(c, 'UNNAMED')}
            for i, c in enumerate(text) if unicodedata.category(c).startswith('P')]


def differences(a, b):
    def edits(left, right):
        return [{'operation': op, 'original': left[i:j], 'enhanced': right[k:l],
                 'original_range': [i, j], 'enhanced_range': [k, l]}
                for op, i, j, k, l in difflib.SequenceMatcher(None, left, right, autojunk=False).get_opcodes()
                if op != 'equal']
    return {'equal': a == b, 'characters': edits(a, b),
            'tokens': edits(re.findall(r'\s+|\w+|[^\w\s]', a), re.findall(r'\s+|\w+|[^\w\s]', b)),
            'original_numbers': numbers(a), 'enhanced_numbers': numbers(b),
            'numbers_equal': numbers(a) == numbers(b),
            'original_punctuation': punctuation(a), 'enhanced_punctuation': punctuation(b),
            'punctuation_sequence_equal': [x['character'] for x in punctuation(a)] ==
                                          [x['character'] for x in punctuation(b)]}


def extract(manifest, output, language="en"):
    from rapidocr import RapidOCR
    import numpy as np
    from PIL import Image
    started = time.perf_counter()
    manifest = Path(manifest)
    m = json.loads(manifest.read_text(encoding='utf-8'))
    engine = RapidOCR(params={'Global.text_score': 0.0, 'Rec.lang_type': language})
    result = {'key': m['key'], 'engine': 'rapidocr',
              'version': importlib.metadata.version('rapidocr'), 'language': language,
              'candidates': [], 'passes': [], 'artifact_hashes': {}}
    # Full-card pass plus enlarged footer: catches tiny print without 20 OCR calls.
    for role in ('original', 'enhanced'):
        name = role + '-aligned.png'
        path = manifest.parent/name
        if sha(path) != m['artifacts'][name]:
            raise ValueError('Changed aligned evidence: ' + name)
        result['artifact_hashes'][name] = sha(path)
        im = Image.open(path).convert('RGB')
        for label, top, scale in [('full', 0, 1), ('footer', int(im.height*.80), 2)]:
            crop = im.crop((0, top, im.width, im.height))
            crop = crop.resize((crop.width*scale, crop.height*scale))
            prediction = engine(np.array(crop)[:, :, ::-1])
            result['passes'].append(role + ':' + label)
            if prediction.boxes is None:
                continue
            for box, text, confidence in zip(prediction.boxes, prediction.txts, prediction.scores):
                polygon = [[float(x)/scale, float(y)/scale + top] for x, y in box]
                result['candidates'].append({'id': f'{role}:{label}:{len(result["candidates"])}',
                    'role': role, 'pass': label, 'text': text, 'confidence': float(confidence),
                    'aligned_polygon': polygon, 'numbers': numbers(text)})
    result['seconds'] = round(time.perf_counter() - started, 3)
    result['note'] = 'Unverified OCR. Multilingual model can misread German marks, foil, tiny print and symbols. Reconcile every candidate and visually add omissions.'
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'output': str(Path(output).resolve()), 'sha256': sha(output),
            'candidates': len(result['candidates']), 'seconds': result['seconds']}


def verify_protocol(m, r):
    """Validate declared visual evidence; cannot certify the reader's perception."""
    issues, unresolved, legibility_flags, typography_flags = [], [], [], []
    region_ids = [x['id'] for x in m['regions']]
    sweep = r.get('reverse_sweep', {})
    if sweep.get('region_ids') != list(reversed(region_ids)) or not sweep.get('evidence'):
        issues.append('Missing ordered bottom-to-top reconciliation sweep.')
    for rid in region_ids:
        region = r.get('regions', {}).get(rid, {})
        items = region.get('items', [])
        for role in ('original', 'enhanced'):
            record = region.get('inventory_reconciliation', {}).get(role, {})
            expected = {i.get('id') for i in items}
            refs = record.get('item_ids', [])
            if (record.get('status') not in ('verified', 'unresolved') or not record.get('evidence')
                    or set(refs) != expected or len(refs) != len(set(refs))):
                issues.append('Missing/inconsistent independent inventory: '+rid+':'+role)
            if record.get('status') == 'unresolved':
                unresolved.append(rid+':'+role+':inventory')
        for item in items:
            if item.get('kind') != 'text':
                continue
            ident = str(item.get('id'))
            typography = item.get('typography', {})
            typ_status = typography.get('status')
            if (typ_status not in ('matched', 'different', 'unresolved', 'not_comparable')
                    or not typography.get('original_evidence') or not typography.get('enhanced_evidence')
                    or not typography.get('description')):
                issues.append('Missing paired typography comparison: '+ident)
            if typ_status in ('different', 'unresolved', 'not_comparable'):
                flag = {'item': ident, **typography}
                if flag not in typography_flags:
                    typography_flags.append(flag)
                # Open visual differences/uncertainty prevent an all-clear even if OCR matches.
                unresolved.append(ident+':typography:'+typ_status)
            for role in ('original', 'enhanced'):
                reading = item.get('readings', {}).get(role, {})
                status = reading.get('status')
                legibility = reading.get('legibility')
                if legibility not in ('clear', 'concern', 'absent'):
                    issues.append('Missing letter-legibility inspection: '+ident+':'+role)
                if (legibility == 'absent') != (status == 'absent'):
                    issues.append('Inconsistent absent/legibility status: '+ident+':'+role)
                concerns = reading.get('legibility_concerns', [])
                if legibility == 'concern' or concerns:
                    unresolved.append(ident+':'+role+':legibility')
                    if legibility != 'concern' or not concerns:
                        issues.append('Incomplete legibility concern: '+ident+':'+role)
                    for concern in concerns:
                        if not all(concern.get(k) for k in ('location', 'description', 'evidence')):
                            issues.append('Missing legibility location/evidence: '+ident+':'+role)
                        flag = {'item': ident, 'role': role, **concern}
                        if flag not in legibility_flags:
                            legibility_flags.append(flag)
                if (status not in ('verified', 'absent', 'unresolved') or not reading.get('evidence')
                        or reading.get('literal') != item.get(role)
                        or reading.get('character_pass') is not True):
                    issues.append('Missing independent character reading: '+ident+':'+role)
                if status == 'absent' and item.get(role) != '':
                    issues.append('Absent reading has nonempty text: '+ident+':'+role)
                if status == 'verified' and not item.get(role):
                    issues.append('Verified reading is empty: '+ident+':'+role)
                if status == 'unresolved':
                    unresolved.append(ident+':'+role+':reading')
    return {'issues': issues, 'unresolved': unresolved, 'legibility_flags': legibility_flags,
            'typography_flags': typography_flags}


def validate(m, r, directory):
    issues, unresolved, diffs = [], [], []
    items = {}
    for region in r.get('regions', {}).values():
        for item in region.get('items', []):
            if item.get('kind') != 'text':
                continue
            ident = item.get('id')
            if ident in items and items[ident] != item:
                issues.append('Conflicting repeated text item: ' + str(ident))
            items[ident] = item
            if not all(isinstance(item.get(role), str) for role in ('original', 'enhanced')):
                continue
            d = differences(item['original'], item['enhanced'])
            if not d['equal']:
                diffs.append({'id': ident, **d})
            if numbers(item['original']) or numbers(item['enhanced']):
                if item.get('numeric_review') not in ('checked', 'different', 'unresolved') or not item.get('numeric_evidence'):
                    issues.append('Missing digit-by-digit review: ' + str(ident))
                elif item['numeric_review'] == 'unresolved':
                    unresolved.append(str(ident))
    extraction = r.get('text_extraction', {})
    if extraction.get('visual_sweep_complete') is not True or not extraction.get('evidence'):
        issues.append('Missing complete visual text extraction sweep.')
    if extraction.get('mode') == 'visual':
        if not extraction.get('ocr_unavailable_reason'):
            issues.append('Visual fallback needs an explicit OCR unavailability reason.')
    elif extraction.get('mode') == 'rapidocr':
        path = Path(directory)/extraction.get('file', '')
        if not path.is_file() or sha(path) != extraction.get('sha256'):
            issues.append('Missing/changed OCR evidence.')
        else:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('key') != m['key']:
                issues.append('OCR belongs to another pair.')
            expected = {role+':'+p for role in ('original', 'enhanced') for p in ('full', 'footer')}
            if set(data.get('passes', [])) != expected:
                issues.append('OCR full-card/footer passes incomplete.')
            for name in ('original-aligned.png', 'enhanced-aligned.png'):
                if data.get('artifact_hashes', {}).get(name) != m['artifacts'].get(name):
                    issues.append('OCR input hash mismatch: ' + name)
            for candidate in data.get('candidates', []):
                resolution = extraction.get('resolutions', {}).get(candidate['id'], {})
                refs = resolution.get('item_ids', [])
                valid = bool(resolution.get('disposition') == 'mapped' and refs and all(x in items for x in refs))
                valid |= resolution.get('disposition') == 'not_printed_text'
                if not valid or not resolution.get('evidence'):
                    issues.append('Unreconciled OCR candidate: ' + candidate['id'])
    else:
        issues.append('Missing text extraction mode.')
    # Required categories force both footer corners and every numeric class into the ledger.
    for field in FIELDS:
        entry = r.get('numeric_fields', {}).get(field, {})
        refs = entry.get('item_ids', [])
        if not entry.get('evidence') or (not refs and entry.get('absent_in_both') is not True):
            issues.append('Missing numeric field coverage: ' + field)
        for ident in refs:
            if ident not in items:
                issues.append('Unknown numeric item: ' + str(ident))
    collector = r.get('numeric_fields', {}).get('collector_number', {}).get('item_ids', [])
    for role in ('original', 'enhanced'):
        value = r.get('identity', {}).get(role, {}).get('card_id')
        if value and value != 'unresolved' and not any(items.get(i, {}).get(role) == value for i in collector):
            issues.append('Collector identity missing from literal inventory: ' + role)
    return {'issues': issues, 'unresolved': unresolved, 'literal_differences': diffs,
            'text_items': len(items), 'numeric_items': sum(bool(numbers(i.get('original', '')) or numbers(i.get('enhanced', ''))) for i in items.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest'); parser.add_argument('--output', required=True)
    parser.add_argument('--language', default='en', help='Recognition language code, e.g. de for German')
    args = parser.parse_args()
    try:
        print(json.dumps(extract(args.manifest, args.output, args.language), indent=2))
    except ImportError as exc:
        raise SystemExit('OCR unavailable; install requirements-ocr.txt or explicitly record a visual extraction fallback. ' + str(exc))
