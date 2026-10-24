import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // contracts are imported as types only (erased at build), so no transpilation of ../../packages is needed
};

export default config;
