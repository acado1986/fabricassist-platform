import { Platform } from 'react-native';
import { secureSession as nativeSession } from './SecureSession.native';
import { secureSession as webSession } from './SecureSession.web';
export const secureSession = Platform.OS === 'web' ? webSession : nativeSession;
