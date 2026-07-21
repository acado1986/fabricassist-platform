import type * as ImagePicker from 'expo-image-picker';

export type CameraCaptureProps = {
  captureLabel: string;
  cancelLabel: string;
  description: string;
  onCaptured: (asset: ImagePicker.ImagePickerAsset) => void;
  onClose: () => void;
  onError: () => void;
  title: string;
  visible: boolean;
};
