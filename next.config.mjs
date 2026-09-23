import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: root,
  // dev: local uvicorn; docker: API_URL set at build time; vercel: api/index.py python function
  rewrites: async () => [
    {
      source: "/api/py/:path*",
      destination: process.env.API_URL
        ? `${process.env.API_URL}/api/py/:path*`
        : process.env.NODE_ENV === "development"
          ? "http://127.0.0.1:8000/api/py/:path*"
          : "/api/",
    },
  ],
  webpack: (config) => {
    config.resolve.alias["@"] = root;
    return config;
  },
};

export default nextConfig;
