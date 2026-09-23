import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: root,
  // dev: proxy to local uvicorn; prod: vercel serves api/index.py as a python function
  rewrites: async () => [
    {
      source: "/api/py/:path*",
      destination:
        process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000/api/py/:path*" : "/api/",
    },
  ],
  webpack: (config) => {
    config.resolve.alias["@"] = root;
    return config;
  },
};

export default nextConfig;
