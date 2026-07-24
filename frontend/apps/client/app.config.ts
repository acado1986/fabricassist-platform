import type { ExpoConfig } from 'expo/config';

const config: ExpoConfig = {
  name: 'FabricAssist',
  slug: 'fabricassist',
  scheme: 'fabricassist',
  version: '0.0.0',
  orientation: 'portrait',
  userInterfaceStyle: 'automatic',
  platforms: ['ios', 'android', 'web'],
  android: { package: 'com.fabricassist.app' },
  ios: { bundleIdentifier: 'com.fabricassist.app' },
  web: { bundler: 'metro', output: 'single' },
  extra: {
    fabricassistApiPublicUrl:
      process.env.FABRICASSIST_API_PUBLIC_URL ?? 'http://localhost:8000',
  },
  plugins: [
    'expo-dev-client',
    'expo-localization',
    'expo-router',
    'expo-secure-store',
    [
      'expo-image-picker',
      {
        cameraPermission:
          'Allow FabricAssist to use your camera to photograph a garment or care label.',
      },
    ],
  ],
  experiments: { typedRoutes: true },
};

export default config;
