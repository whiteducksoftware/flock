/**
 * Image fields in artifact schemas (#511).
 *
 * `flock.Image` marks its JSON schema with `"x-flock-image": true`. A field is an
 * image field if it refers to such a definition: `Image`, `Image | None`
 * (`anyOf` with null) or `list[Image]` (`items`).
 */

export type ImageFieldKind = 'one' | 'many';

/** File types the dashboard offers; the server accepts the same set for uploads. */
export const IMAGE_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp,image/bmp';

/** Longest side of a picture after it is scaled down in the browser. */
export const MAX_SIDE = 1024;

function resolveRef(node: any, schema: any): any {
  if (node && typeof node.$ref === 'string' && node.$ref.startsWith('#/$defs/')) {
    return schema?.$defs?.[node.$ref.slice('#/$defs/'.length)];
  }
  return node;
}

function isImageSchema(node: any, schema: any): boolean {
  return resolveRef(node, schema)?.['x-flock-image'] === true;
}

export function imageFieldKind(prop: any, schema: any): ImageFieldKind | null {
  if (!prop) return null;
  if (isImageSchema(prop, schema)) return 'one';
  const options: any[] = Array.isArray(prop.anyOf) ? prop.anyOf : [];
  const nonNull = options.filter((option) => option?.type !== 'null');
  if (nonNull.length === 1) return imageFieldKind(nonNull[0], schema);
  if (prop.type === 'array' && isImageSchema(prop.items, schema)) return 'many';
  return null;
}

/** PNG for formats that can be transparent (as `Image.from_pil` keeps alpha), else JPEG. */
export function outputType(fileType: string): 'image/png' | 'image/jpeg' {
  return ['image/png', 'image/gif', 'image/webp'].includes(fileType) ? 'image/png' : 'image/jpeg';
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error(`Could not read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

/**
 * A picture as a `data:image/...` URL, scaled down to `maxSide` and re-encoded in
 * the browser when it can draw images, which also drops metadata such as GPS
 * positions. The server validates the result either way.
 */
export async function fileToImageUrl(file: File, maxSide: number = MAX_SIDE): Promise<string> {
  const original = await readAsDataUrl(file);
  if (typeof createImageBitmap !== 'function' || typeof document === 'undefined') {
    return original;
  }
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context) return original;
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close?.();
    return canvas.toDataURL(outputType(file.type), 0.9);
  } catch {
    return original;
  }
}
