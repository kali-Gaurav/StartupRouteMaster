import js from '@eslint/js';
import globals from 'globals';
import eslintReact from '@eslint-react/eslint-plugin';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', '.venv', 'venv', '__pycache__'] },
  {
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      eslintReact.configs.recommended, // Add this line
    ],
    // limit linting to the frontend source and the Vite config to avoid
    // picking up unrelated TypeScript files from Python virtualenvs
    files: ['src/**/*.{ts,tsx}', 'vite.config.ts'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: { // Remove '@eslint-react': eslintReact,
      'react-refresh': reactRefresh,
    },
    rules: { 'react-refresh/only-export-components': 'off',
      // Remove ...eslintReact.configs.recommended.rules,
      // ensure the TypeScript variant of this rule has explicit options
      '@typescript-eslint/no-unused-expressions': [
        'error',
        { allowShortCircuit: true, allowTernary: true, allowTaggedTemplates: true }
      ],
    },
  }
);



