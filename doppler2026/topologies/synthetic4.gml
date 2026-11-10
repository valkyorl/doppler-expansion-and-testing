graph [
  name "synthetic4"
  draws 1
  generator_nodes "4"
  generator_mean_degree "3.0"
  generator_nearest_first "2"
  generator_side_km "1500.0"
  generator_center "(41.5, -90.0)"
  generator_capacity "100000000000.0"
  generator_seed "0"
  node [
    id 0
    label "0"
    Latitude 38.39795248514019
    Longitude -87.5358847488966
  ]
  node [
    id 1
    label "1"
    Latitude 34.98537058293922
    Longitude -98.25847112758147
  ]
  node [
    id 2
    label "2"
    Latitude 47.06174421412668
    Longitude -84.36386927448957
  ]
  node [
    id 3
    label "3"
    Latitude 44.592389880309
    Longitude -88.08148653451943
  ]
  edge [
    source 0
    target 2
    capacity 100000000000.0
  ]
  edge [
    source 0
    target 1
    capacity 100000000000.0
  ]
  edge [
    source 0
    target 3
    capacity 100000000000.0
  ]
  edge [
    source 1
    target 3
    capacity 100000000000.0
  ]
  edge [
    source 1
    target 2
    capacity 100000000000.0
  ]
  edge [
    source 2
    target 3
    capacity 100000000000.0
  ]
]
