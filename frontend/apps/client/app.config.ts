import type { ExpoConfig } from 'expo/config';

const config: ExpoConfig = {
  name: 'FabricAssist',
  slug: 'fabricassist',
  scheme: 'fabricassist',
  version: '0.0.0',
  orientation: 'portrait',
  userInterfaceStyle: 'automatic',
  platforms: ['ios', 'android', 'web'],
  web: { bundler: 'metro', output: 'single' },
  extra: {
    fabricassistApiPublicUrl:
      process.env.FABRICASSIST_API_PUBLIC_URL ?? 'http://localhost:8000',
  },
  plugins: ['expo-localization', 'expo-router'],
  experiments: { typedRoutes: true },
};

export default config;
