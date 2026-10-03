## Group points with a dict instead of sorting

**Context:** points that share a voxel have to be brought together before averaging.
**Options:** A — sort the points by voxel key and average runs; B — accumulate sums in a dict keyed by voxel.
**Chosen:** B
**Why:** a dict is a single O(n) pass with no extra copy of the points, and gridsnap has no numpy dependency that would make a vectorised sort cheap.
**Trade-offs:** memory grows with the number of occupied voxels. With numpy available, a `np.unique` over the keys would be faster for large clouds.
