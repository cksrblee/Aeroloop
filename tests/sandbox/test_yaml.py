import yaml
with open('/root/projects/AeroLoop/src/aeroloop/design/openvsp_maximal_geometry_template.yaml') as f:
    d = yaml.safe_load(f)
for k, v in d['components'].items():
    if 'control_surfaces' in v:
        print(f"{k} has control_surfaces")
    if 'subsurfaces' in v:
        print(f"{k} has subsurfaces")
    if '_control_surfaces' in v:
        print(f"{k} has _control_surfaces")
