"""One-process, same-origin demo launcher. No public hosting or secret output."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def preflight(analysis=False):
    problems = []
    for module in ('fastapi', 'uvicorn', 'fitz', 'multipart'):
        if importlib.util.find_spec(module) is None:
            problems.append(f'Missing {module}; install backend/requirements.txt in your Python environment.')
    for name in ('pdf.mjs', 'pdf.worker.mjs'):
        if not (ROOT / 'frontend/node_modules/pdfjs-dist/build' / name).is_file():
            problems.append('PDF preview dependency missing; run npm --prefix frontend ci.')
            break
    if not shutil.which('tesseract'):
        problems.append('Tesseract is missing; install it to process scanned PDFs (apt install tesseract-ocr or brew install tesseract).')
    if analysis:
        if importlib.util.find_spec('anthropic') is None:
            problems.append('Install backend/requirements-analysis.txt for AI extraction.')
        for name in ('ANTHROPIC_API_KEY', 'IHH_ANALYSIS_MODEL'):
            if not os.environ.get(name):
                problems.append(f'{name} is not configured; set it securely on the server, never in frontend code or chat.')
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check prerequisites without starting or making model calls')
    parser.add_argument('--analysis', action='store_true', help='Enable the real extraction adapter with configured credentials/model')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose a port between 1024 and 65535.')
    problems = preflight(args.analysis)
    if problems:
        print('Demo prerequisites need attention:')
        for problem in problems:
            print('- ' + problem)
        return 1
    print('Prerequisites available: frontend preview, PDF parsing and scanned-page OCR.')
    print('AI extraction: configured for startup; model availability is not validated.' if args.analysis else 'AI extraction: off. OCR/manual source review only; no model calls.')
    print('Records are temporary and are removed when this process stops. No messages are sent.')
    if args.check:
        return 0
    os.environ['IHH_ANALYSIS_ADAPTER'] = 'backend.extraction:create_adapter' if args.analysis else ''
    import uvicorn
    print(f'Open the server root on this laptop: http://127.0.0.1:{args.port}/')
    uvicorn.run('backend.app:app', host='127.0.0.1', port=args.port, access_log=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
