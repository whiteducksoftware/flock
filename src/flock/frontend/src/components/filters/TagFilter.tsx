import React from 'react';
import MultiSelect from '../settings/MultiSelect';
import { useFilterStore } from '../../store/filterStore';

const TagFilter: React.FC = () => {
  const options = useFilterStore((state) => state.availableTags);
  const selected = useFilterStore((state) => state.selectedTags);
  const setTags = useFilterStore((state) => state.setTags);

  return (
    <MultiSelect
      options={options}
      selected={selected}
      onChange={setTags}
      placeholder={options.length ? 'Select tags…' : 'No tags available'}
      disabled={options.length === 0}
    />
  );
};

export default TagFilter;
