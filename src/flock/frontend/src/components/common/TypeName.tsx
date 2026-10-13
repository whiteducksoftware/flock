import React from 'react';
import { shortTypeName } from '../../utils/typeName';

/** A type name in the mono face, without its module path; the full name is the tooltip. */
const TypeName: React.FC<{ name: string; className?: string }> = ({ name, className }) => (
  <span
    className={className}
    title={name}
    style={{ fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}
  >
    {shortTypeName(name)}
  </span>
);

export default TypeName;
