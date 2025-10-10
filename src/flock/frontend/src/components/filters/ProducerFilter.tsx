import React from 'react';
import MultiSelect from '../settings/MultiSelect';
import { useFilterStore } from '../../store/filterStore';

const ProducerFilter: React.FC = () => {
  const options = useFilterStore((state) => state.availableProducers);
  const selected = useFilterStore((state) => state.selectedProducers);
  const setProducers = useFilterStore((state) => state.setProducers);

  return (
    <MultiSelect
      options={options}
      selected={selected}
      onChange={setProducers}
      placeholder={options.length ? 'Select producers…' : 'No producers'}
      disabled={options.length === 0}
    />
  );
};

export default ProducerFilter;
