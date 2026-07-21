import { useEffect, useRef } from 'react';
import * as ImagePicker from 'expo-image-picker';

import type { CameraCaptureProps } from './CameraCapture.types';

/** Uses the device camera; the web implementation renders an in-browser viewfinder. */
export function CameraCapture({
  onCaptured,
  onClose,
  onError,
  visible,
}: CameraCaptureProps): null {
  const launched = useRef(false);

  useEffect(() => {
    if (!visible) {
      launched.current = false;
      return;
    }
    if (launched.current) return;
    launched.current = true;

    async function openCamera(): Promise<void> {
      try {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          onError();
          return;
        }
        const result = await ImagePicker.launchCameraAsync({
          mediaTypes: ['images'],
          quality: 1,
        });
        if (result.canceled) {
          onClose();
          return;
        }
        const [asset] = result.assets;
        if (!asset) {
          onError();
          return;
        }
        onCaptured(asset);
      } catch {
        onError();
      }
    }

    void openCamera();
  }, [onCaptured, onClose, onError, visible]);

  return null;
}
