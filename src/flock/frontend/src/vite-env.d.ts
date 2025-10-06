/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare const __BUILD_TIMESTAMP__: string;
declare const __BUILD_HASH__: string;

declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}
