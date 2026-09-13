export type ExtensionMismatchInfo = {
  extension: string;
  actualType: string;
  suggestedExtension: string | null;
  suggestion: string;
};

const suggestedExtensions: Record<string, string> = {
  csv: "csv",
  docx: "docx",
  json: "json",
  markdown: "md",
  pdf: "pdf",
  srt: "srt",
  text: "txt",
  xlsx: "xlsx",
  yaml: "yaml",
  zip: "zip",
};

export function parseExtensionMismatch(message: string): ExtensionMismatchInfo | null {
  const match = message.match(
    /文件扩展名是\s+\.([a-z0-9]+)，但真实内容是\s+([a-z0-9_-]+)，请确认文件类型/i,
  );
  if (!match) return null;

  const extension = match[1].toLowerCase();
  const actualType = match[2].toLowerCase();
  const suggestedExtension = suggestedExtensions[actualType] ?? null;
  const suggestion = suggestedExtension
    ? `请上传真正的 .${extension} 文件，或将当前文件扩展名改为 .${suggestedExtension} 后重试。`
    : `请上传真正的 .${extension} 文件，或根据实际内容修正文件扩展名后重试。`;

  return { extension, actualType, suggestedExtension, suggestion };
}
