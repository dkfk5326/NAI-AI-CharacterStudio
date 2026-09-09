from .config import read_yaml

def suggestions(adapter,ids,mapping=None,**options):
    groups=adapter.get_character_related_tags(ids,**options)
    mapping=mapping if mapping is not None else read_yaml('knowledge/field-taxonomy-map.yaml')['mapping']
    # Taxonomy grouping requires exact supporting node keys. Missing taxonomy remains unclassified.
    if adapter.has('taxonomy_tag_memberships','taxonomy_node_id','tag_id') and adapter.has('taxonomy_nodes','id','node_key'):
        with adapter.connect() as c:
            for items in groups.values():
                for item in items:
                    keys=[r[0] for r in c.execute('SELECT n.node_key FROM taxonomy_nodes n JOIN taxonomy_tag_memberships m ON m.taxonomy_node_id=n.id WHERE m.tag_id=?',(item['tag_id'],))]
                    fields=[f for f,known in mapping.items() if any(k in known for k in keys)]
                    item['field']=fields[0] if len(fields)==1 else 'unclassified';item['taxonomy_keys']=keys
    return groups
