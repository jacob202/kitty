/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  allowedDevOrigins: ['172.16.1.161', '192.168.*', '10.*', '172.16.*'],
  images: { unoptimized: true },
};

module.exports = nextConfig;
