/**
 * The composer's form values and the payload they publish. A form value has
 * the shape its input needs: a list is one item per line, a picture is a
 * PickedImage. Form and JSON mode share these conversions.
 */

import { imageFieldKind, isNullable } from '../../utils/imageFields';

export type FormValues = Record<string, any>;

/** A picture chosen in the form: shown as a preview, published as an Image. */
export interface PickedImage {
  name: string;
  url: string;
}

/** An artifact type's JSON schema, as `/api/artifact-types` serves it. */
export type Schema = { properties?: Record<string, any>; required?: string[]; [key: string]: any };

/** The empty form of a type: schema defaults where there are some. */
export function initialFormData(schema: Schema): FormValues {
  const initialData: FormValues = {};
  Object.entries(schema.properties ?? {}).forEach(([key, prop]) => {
    const imageKind = imageFieldKind(prop, schema);
    if (imageKind) {
      initialData[key] = imageKind === 'many' ? [] : null;
    } else if (prop.type === 'boolean') {
      initialData[key] = false;
    } else if (prop.type === 'array') {
      // Represent arrays (e.g. list[str] / list[int]) as a newline-separated string in the UI.
      // If the schema has a default (e.g. default_factory=list), show it to the user.
      initialData[key] = Array.isArray(prop.default) ? prop.default.join('\n') : '';
    } else {
      initialData[key] = prop.default ?? '';
    }
  });
  return initialData;
}

/** The fewest pictures a list of images takes (`minItems`, else none). */
export function minPictures(prop: any): number {
  const arraySchema = prop.anyOf?.find((option: any) => option?.type === 'array') ?? prop;
  return arraySchema.minItems ?? 0;
}

/**
 * Whether the form asks for a value:
 * - If schema.required lists the field, it's required.
 * - If field has an explicit default, treat as optional.
 * - Arrays default to optional unless explicitly required.
 * - Scalar fields with no default are treated as required.
 * - A picture is required unless the field has a default or may be None;
 *   a list of pictures only with a minimum.
 */
export function isRequiredField(key: string, prop: any, schema: Schema): boolean {
  const isExplicitlyRequired = Array.isArray(schema.required) && schema.required.includes(key);
  const hasDefault = prop.default !== undefined;
  const imageKind = imageFieldKind(prop, schema);
  if (imageKind === 'many') return minPictures(prop) > 0;
  if (imageKind === 'one') return (isExplicitlyRequired || !hasDefault) && !isNullable(prop);
  return isExplicitlyRequired || (!hasDefault && prop.type !== 'array');
}

const PYTHON_TYPES: Record<string, string> = {
  string: 'str',
  integer: 'int',
  number: 'float',
  boolean: 'bool',
  object: 'dict',
};

/** A field's type as Python writes it: `str`, `list[int]`, `Image | None`. */
export function fieldType(prop: any, schema: Schema): string {
  if (!prop) return 'any';
  const imageKind = imageFieldKind(prop, schema);
  if (imageKind && !isNullable(prop)) return imageKind === 'many' ? 'list[Image]' : 'Image';
  if (Array.isArray(prop.anyOf)) {
    return prop.anyOf.map((option: any) => (option?.type === 'null' ? 'None' : fieldType(option, schema))).join(' | ');
  }
  if (typeof prop.$ref === 'string') return prop.$ref.split('/').pop();
  if (Array.isArray(prop.enum)) return 'enum';
  if (prop.type === 'array') return prop.items ? `list[${fieldType(prop.items, schema)}]` : 'list';
  return PYTHON_TYPES[prop.type] ?? prop.type ?? 'any';
}

/** The payload the form publishes: each value converted to its schema type. */
export function formToPayload(formData: FormValues, schema: Schema): Record<string, any> {
  const processedData: Record<string, any> = {};
  Object.entries(formData).forEach(([key, value]) => {
    const prop = schema.properties?.[key];
    if (!prop) return; // not a field of this type
    const imageKind = imageFieldKind(prop, schema);
    if (imageKind === 'many') {
      const images = value as PickedImage[];
      // No pictures chosen: keep the schema default (e.g. None or a preset list)
      if (images.length > 0 || prop.default === undefined) {
        processedData[key] = images.map((image) => ({ url: image.url }));
      }
    } else if (imageKind === 'one') {
      if (value) {
        processedData[key] = { url: (value as PickedImage).url };
      } else if (isNullable(prop) && prop.default === undefined) {
        processedData[key] = null; // required, but may be None
      } // otherwise the schema default applies
    } else if (prop.type === 'number' || prop.type === 'integer') {
      processedData[key] = Number(value);
    } else if (prop.type === 'boolean') {
      processedData[key] = Boolean(value);
    } else if (prop.type === 'array') {
      // Convert newline-separated string into arrays for list-like fields
      if (prop.items && prop.items.type === 'string') {
        if (typeof value === 'string') {
          processedData[key] = lines(value);
        } else if (Array.isArray(value)) {
          processedData[key] = value;
        } else {
          processedData[key] = [];
        }
      } else if (prop.items && (prop.items.type === 'number' || prop.items.type === 'integer')) {
        if (typeof value === 'string') {
          processedData[key] = lines(value)
            .map((v: string) => Number(v))
            .filter((v: number) => !Number.isNaN(v));
        } else if (Array.isArray(value)) {
          processedData[key] = value.map((v: any) => Number(v));
        } else {
          processedData[key] = [];
        }
      } else {
        // For other array item types, pass through as-is for now
        processedData[key] = value;
      }
    } else {
      processedData[key] = value;
    }
  });
  return processedData;
}

/** The non-empty lines of a list field, trimmed. */
export function lines(value: string): string[] {
  return value
    .split('\n')
    .map((v: string) => v.trim())
    .filter((v: string) => v.length > 0);
}

const isImage = (value: any): value is { url: string } =>
  value !== null && typeof value === 'object' && typeof value.url === 'string';

/** The form of a payload (JSON mode back to the form); missing fields get their empty value. */
export function payloadToForm(payload: Record<string, any>, schema: Schema): FormValues {
  const values = initialFormData(schema);
  Object.entries(schema.properties ?? {}).forEach(([key, prop]) => {
    if (!(key in payload)) return;
    const value = payload[key];
    const imageKind = imageFieldKind(prop, schema);
    if (imageKind === 'many') {
      const images = Array.isArray(value) ? value.filter(isImage) : [];
      values[key] = images.map((image, index) => ({ name: `${key} ${index + 1}`, url: image.url }));
    } else if (imageKind === 'one') {
      values[key] = isImage(value) ? { name: key, url: value.url } : null;
    } else if (prop.type === 'boolean') {
      values[key] = Boolean(value);
    } else if (prop.type === 'array' && Array.isArray(value) && value.every((item) => typeof item !== 'object')) {
      values[key] = value.join('\n'); // one item per line
    } else {
      values[key] = value ?? '';
    }
  });
  return values;
}
