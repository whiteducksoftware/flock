class MemoryMappingParser:
    """Parses memory mapping declarations into executable operations."""
    
    def parse(self, mapping: str) -> list[dict[str, Any]]:
        """Parse a memory mapping string into operations.
        
        Example mapping:
        "topic -> memory.semantic(0.9) | memory.exact -> output"
        
        Returns list of operations with their configs.
        """
        operations = []
        
        # Split into stages
        stages = mapping.split('|')
        
        for stage in stages:
            if '->' not in stage:
                continue
                
            inputs, op_spec = stage.split('->')
            
            # Parse operation specification
            if 'memory.' in op_spec:
                op_name = op_spec.split('.')[1]
                op_config = self._parse_operation_config(op_name, op_spec)
                
                operations.append({
                    'inputs': [i.strip() for i in inputs.split(',')],
                    'operation': op_config
                })
        
        return operations