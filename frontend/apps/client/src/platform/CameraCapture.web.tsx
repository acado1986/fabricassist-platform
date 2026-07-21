import { useEffect, useRef } from 'react';
import type * as ImagePicker from 'expo-image-picker';

import type { CameraCaptureProps } from './CameraCapture.types';

function stop(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}

/** Renders a real browser camera viewfinder instead of opening the file picker. */
export function CameraCapture({
  captureLabel,
  cancelLabel,
  description,
  onCaptured,
  onClose,
  onError,
  title,
  visible,
}: CameraCaptureProps): React.ReactNode {
  const stream = useRef<MediaStream | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (!visible) return;
    let active = true;

    async function startCamera(): Promise<void> {
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: 'environment' } },
        });
        if (!active) {
          stop(media);
          return;
        }
        stream.current = media;
        if (video.current) {
          video.current.srcObject = media;
          await video.current.play();
        }
      } catch {
        if (active) onError();
      }
    }

    void startCamera();
    return () => {
      active = false;
      stop(stream.current);
      stream.current = null;
    };
  }, [onError, visible]);

  function close(): void {
    stop(stream.current);
    stream.current = null;
    onClose();
  }

  function capture(): void {
    const currentVideo = video.current;
    if (
      !currentVideo ||
      !currentVideo.videoWidth ||
      !currentVideo.videoHeight
    ) {
      onError();
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = currentVideo.videoWidth;
    canvas.height = currentVideo.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) {
      onError();
      return;
    }
    context.drawImage(currentVideo, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          onError();
          return;
        }
        const asset: ImagePicker.ImagePickerAsset = {
          assetId: null,
          base64: null,
          duration: null,
          exif: null,
          fileName: 'fabricassist-camera.jpg',
          fileSize: blob.size,
          height: canvas.height,
          mimeType: 'image/jpeg',
          type: 'image',
          uri: URL.createObjectURL(blob),
          width: canvas.width,
        };
        stop(stream.current);
        stream.current = null;
        onCaptured(asset);
      },
      'image/jpeg',
      0.9,
    );
  }

  if (!visible) return null;

  return (
    <div aria-modal="true" role="dialog" style={styles.backdrop}>
      <div aria-labelledby="camera-capture-title" style={styles.dialog}>
        <h2 id="camera-capture-title" style={styles.title}>
          {title}
        </h2>
        <p style={styles.description}>{description}</p>
        <video autoPlay muted playsInline ref={video} style={styles.video} />
        <div style={styles.actions}>
          <button onClick={close} style={styles.secondaryButton} type="button">
            {cancelLabel}
          </button>
          <button onClick={capture} style={styles.primaryButton} type="button">
            {captureLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  actions: { display: 'flex', gap: 12, justifyContent: 'flex-end' },
  backdrop: {
    alignItems: 'center',
    background: 'rgba(17, 35, 29, 0.7)',
    display: 'flex',
    inset: 0,
    justifyContent: 'center',
    padding: 20,
    position: 'fixed',
    zIndex: 1000,
  },
  description: { color: '#536960', lineHeight: 1.5, margin: '0 0 16px' },
  dialog: {
    background: '#ffffff',
    borderRadius: 16,
    boxShadow: '0 20px 48px rgba(17, 35, 29, 0.28)',
    maxWidth: 620,
    padding: 24,
    width: '100%',
  },
  primaryButton: {
    background: '#21775e',
    border: 0,
    borderRadius: 10,
    color: '#ffffff',
    cursor: 'pointer',
    fontSize: 15,
    fontWeight: 700,
    minHeight: 44,
    padding: '0 18px',
  },
  secondaryButton: {
    background: '#ffffff',
    border: '1px solid #bfd3cb',
    borderRadius: 10,
    color: '#18362d',
    cursor: 'pointer',
    fontSize: 15,
    fontWeight: 700,
    minHeight: 44,
    padding: '0 18px',
  },
  title: { color: '#18362d', fontSize: 22, margin: '0 0 8px' },
  video: {
    background: '#11231d',
    borderRadius: 12,
    display: 'block',
    marginBottom: 16,
    maxHeight: '60vh',
    objectFit: 'cover',
    width: '100%',
  },
};
