import type {
  BinaryUploadRequest,
  BinaryUploadResult,
} from './BinaryUpload.types';

export async function uploadBinaryFile({
  fileUri,
  headers,
  url,
}: BinaryUploadRequest): Promise<BinaryUploadResult> {
  const image = await fetch(fileUri);
  const blob = await image.blob();
  const response = await fetch(url, {
    method: 'PUT',
    headers,
    body: blob,
  });

  return { ok: response.ok, status: response.status };
}
