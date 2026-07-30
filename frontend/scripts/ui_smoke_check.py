"""Lightweight smoke check for UI deps used by GitHub Actions workflow."""
import sys

try:
    import streamlit
    import pandas
except Exception as e:
    print('IMPORT_ERROR', e, file=sys.stderr)
    raise

print('streamlit', streamlit.__version__)
print('pandas', pandas.__version__)
