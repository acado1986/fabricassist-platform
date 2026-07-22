import * as FileSystem from 'expo-file-system/legacy';

import type {
  BinaryUploadRequest,
  BinaryUploadResult,
} from './BinaryUpload.types';

export async function uploadBinaryFile({
  fileUri,
  headers,
  url,
}: BinaryUploadRequest): Promise<BinaryUploadResult> {
  const response = await FileSystem.uploadAsync(url, fileUri, {
    headers,
    httpMethod: 'PUT',
    uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
  });

  return {
    ok: response.status >= 200 && response.status < 300,
    status: response.status,
  };
}
