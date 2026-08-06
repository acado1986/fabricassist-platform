import { APP_VERSION } from './src/config/version';
import type { ExpoConfig } from 'expo/config';

const config: ExpoConfig = {
  name: 'FabricAssist',
  slug: 'fabricassist',
  scheme: 'fabricassist',
  version: APP_VERSION,
  orientation: 'portrait',
  userInterfaceStyle: 'automatic',
  platforms: ['ios', 'android', 'web'],
  android: { package: 'com.fabricassist.app' },
  ios: { bundleIdentifier: 'com.fabricassist.app' },
  web: { bundler: 'metro', output: 'static' },
  extra: {
    fabricassistApiPublicUrl:
      process.env.EXPO_PUBLIC_FABRICASSIST_API_URL ?? 'http://localhost:8000',
    fabricassistEnvironment:
      process.env.EXPO_PUBLIC_FABRICASSIST_ENVIRONMENT ?? 'development',
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
