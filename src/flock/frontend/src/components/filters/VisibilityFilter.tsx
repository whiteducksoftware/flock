import React from 'react';
import MultiSelect from '../settings/MultiSelect';
import { useFilterStore } from '../../store/filterStore';

const VisibilityFilter: React.FC = () => {
  const options = useFilterStore((state) => state.availableVisibility);
  const selected = useFilterStore((state) => state.selectedVisibility);
  const setVisibility = useFilterStore((state) => state.setVisibility);

  return (
    <MultiSelect
      options={options}
      selected={selected}
      onChange={setVisibility}
      placeholder={options.length ? 'Select visibility…' : 'No visibility options'}
      disabled={options.length === 0}
    />
  );
};

export default VisibilityFilter;
