export type ExtensionMismatchInfo = {
  extension: string;
  actualType: string;
  suggestedExtension: string | null;
  suggestion: string;
};

const suggestedExtensions: Record<string, string> = {
  bmp: "bmp",
  csv: "csv",
  docx: "docx",
  json: "json",
  gif: "gif",
  jpg: "jpg",
  markdown: "md",
  pdf: "pdf",
  png: "png",
  srt: "srt",
  text: "txt",
  xlsx: "xlsx",
  yaml: "yaml",
  webp: "webp",
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

export type ImageErrorInfo = {
  title: string;
  suggestion: string;
  warning: boolean;
  dimensions: { totalPixels: number; limit: number } | null;
};

export function parseImageError(message: string): ImageErrorInfo | null {
  const normalized = message.toLowerCase();
  const oversized = message.match(
    /图片尺寸过大（(\d+)\s*像素），超过限制（(\d+)\s*像素），已拒绝转换/,
  );
  if (oversized) {
    const totalPixels = Number(oversized[1]);
    const limit = Number(oversized[2]);
    return {
      title: "图片尺寸超过安全限制",
      suggestion: `检测到 ${totalPixels.toLocaleString("zh-CN")} 像素，安全上限为 ${limit.toLocaleString("zh-CN")} 像素。请缩小图片尺寸后重试。`,
      warning: false,
      dimensions: { totalPixels, limit },
    };
  }
  if (normalized.includes("image decode error") || message.includes("图片无法解码")) {
    return {
      title: "图片无法解码",
      suggestion: "请确认图片未损坏，并重新导出或下载原始图片后重试。",
      warning: false,
      dimensions: null,
    };
  }
  if (normalized.includes("image encode error") || message.includes("图片编码失败")) {
    return {
      title: "图片编码失败",
      suggestion: "目标格式可能不支持当前图片的色彩模式或透明等特性。",
      warning: false,
      dimensions: null,
    };
  }
  if (normalized.includes("image lossy warning") || message.includes("有损转换") || message.includes("只保留第一帧")) {
    return {
      title: "图片转换质量提醒",
      suggestion: message.includes("只保留第一帧")
        ? "GIF 已成功转换，但 PNG 结果只包含动画第一帧。"
        : "转换已成功，但压缩可能造成画质下降。",
      warning: true,
      dimensions: null,
    };
  }
  return null;
}
