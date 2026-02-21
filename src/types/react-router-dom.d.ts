// Temporary type stub for `react-router-dom` — remove when the package + types are installed
// This file prevents TS errors in the editor while `npm install` / registry auth is fixed.

declare module 'react-router-dom' {
  import React from 'react';

  export type NavigateFunction = (to: string | number, options?: { replace?: boolean; state?: unknown }) => void;

  export const BrowserRouter: React.ComponentType<{ children?: React.ReactNode }>;
  export const Routes: React.ComponentType<{ children?: React.ReactNode }>;
  export const Route: React.ComponentType<{ path?: string; element?: React.ReactNode; children?: React.ReactNode }>;
  export const useNavigate: () => NavigateFunction;
  export const useSearchParams: () => [URLSearchParams, (nextInit: URLSearchParamsInit) => void];
  export function useParams<T extends Record<string, string | undefined> = Record<string, string | undefined>>(): T;
  export const useLocation: () => { pathname: string; search: string; hash: string; state: unknown; key: string };
  export const Outlet: React.ComponentType<{ context?: unknown }>;
  export const Navigate: React.ComponentType<{ to: string; replace?: boolean; state?: unknown }>;
  export const Link: React.ComponentType<{ to: string; replace?: boolean; state?: unknown; className?: string; children?: React.ReactNode; target?: string }>;
  export const NavLink: React.ComponentType<{ to: string; end?: boolean; className?: string | ((props: { isActive: boolean }) => string); children?: React.ReactNode }>;

  export type URLSearchParamsInit = string | string[][] | Record<string, string> | URLSearchParams;

  const _default: unknown;
  export default _default;
}
