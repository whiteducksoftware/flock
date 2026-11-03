/**
 * Checks a payload against its type's JSON schema before JSON mode sends it:
 * an object, the required fields present, each field's type (a list's item
 * type too), null where an `anyOf` allows it, enum members. A nested object
 * is only checked for being an object; the server validates the rest.
 */

import type { Schema } from './form';

/** The key of a problem with the payload as a whole. */
export const ROOT = '$';

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

function resolve(node: any, schema: Schema): any {
  if (node && typeof node.$ref === 'string' && node.$ref.startsWith('#/$defs/')) {
    return schema.$defs?.[node.$ref.slice('#/$defs/'.length)];
  }
  return node;
}

const typesOf = (node: any): string[] =>
  node.type === undefined ? [] : Array.isArray(node.type) ? node.type : [node.type];

function isOfType(value: unknown, type: string): boolean {
  switch (type) {
    case 'string':
      return typeof value === 'string';
    case 'number':
      return typeof value === 'number' && Number.isFinite(value);
    case 'integer':
      return Number.isInteger(value);
    case 'boolean':
      return typeof value === 'boolean';
    case 'null':
      return value === null;
    case 'object':
      return isObject(value);
    case 'array':
      return Array.isArray(value);
    default:
      return true;
  }
}

/** True if `value` fits the schema `node`. */
function fits(value: unknown, node: any, schema: Schema): boolean {
  node = resolve(node, schema);
  if (!isObject(node)) return true; // no constraint we know
  const options = node.anyOf ?? node.oneOf;
  if (Array.isArray(options) && !options.some((option) => fits(value, option, schema))) return false;
  if (Array.isArray(node.enum) && !node.enum.includes(value)) return false;
  const types = typesOf(node);
  if (types.length > 0 && !types.some((type) => isOfType(value, type))) return false;
  if (Array.isArray(value) && node.items) return value.every((item) => fits(item, node.items, schema));
  return true;
}

const NOUNS: Record<string, [string, string]> = {
  string: ['a string', 'strings'],
  number: ['a number', 'numbers'],
  integer: ['an integer', 'integers'],
  boolean: ['true or false', 'booleans'],
  null: ['null', 'nulls'],
  object: ['an object', 'objects'],
  array: ['a list', 'lists'],
};

/** What fits `node`, for a message: `a string or null`, `a list of integers`. */
function describe(node: any, schema: Schema, plural = false): string {
  node = resolve(node, schema);
  if (!isObject(node)) return plural ? 'values' : 'a value';
  const options = node.anyOf ?? node.oneOf;
  if (Array.isArray(options)) return options.map((option) => describe(option, schema, plural)).join(' or ');
  if (Array.isArray(node.enum)) return `${plural ? 'values out of' : 'one of'} ${node.enum.map(String).join(', ')}`;
  const types = typesOf(node);
  if (types.length === 0) return plural ? 'values' : 'a value';
  return types
    .map((type) => {
      if (type === 'array' && node.items) return `${plural ? 'lists' : 'a list'} of ${describe(node.items, schema, true)}`;
      const [one, many] = NOUNS[type] ?? [`a ${type}`, `${type} values`];
      return plural ? many : one;
    })
    .join(' or ');
}

/** Problems of `value` as a payload of `schema`, by field (`ROOT` for the payload); empty if none. */
export function schemaErrors(value: unknown, schema: Schema): Record<string, string> {
  if (!isObject(value)) return { [ROOT]: 'The payload must be a JSON object' };
  const errors: Record<string, string> = {};
  const required = Array.isArray(schema.required) ? schema.required : [];
  required.forEach((key) => {
    if (value[key] === undefined) errors[key] = `${key} is required`;
  });
  Object.entries(schema.properties ?? {}).forEach(([key, prop]) => {
    if (value[key] === undefined || fits(value[key], prop, schema)) return;
    errors[key] = `${key} must be ${describe(prop, schema)}`;
  });
  return errors;
}
