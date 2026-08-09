# Materials and PBR

- Segment meaningful material regions before estimating maps.
- Keep baseColor, roughness, metalness, normal/bump and confidence aligned when
  correcting or reference-locking a region.
- Deliver glTF metallic-roughness with roughness in G, metalness in B; base
  color is sRGB and MR is linear.
- Reject baked illumination/reflection in albedo and one-material treatment of
  mixed paint, metal, rubber, glass, skin, hair or cloth.
- Bare metal is predominantly metallic; paint, rust, skin, hair/fur, fabric,
  plastic, rubber, ceramic, glass, concrete and wood are dielectric regions.
- Require normals for master skin, hair/fur, fabric, concrete, wood and damaged
  metal. Use clearcoat, sheen, transmission, volume and IOR only when target
  runtime and fallback are validated.
- Record evidence and unobserved texels per region. A pleasing front texture
  cannot promote inconsistent quarter views or maps.
- Review under changing neutral illumination; automatic metrics may reject but
  cannot self-certify artistic excellence.

