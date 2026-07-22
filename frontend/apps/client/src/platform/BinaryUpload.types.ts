export type BinaryUploadRequest = {
  fileUri: string;
  headers: Record<string, string>;
  url: string;
};

export type BinaryUploadResult = {
  ok: boolean;
  status: number;
};
