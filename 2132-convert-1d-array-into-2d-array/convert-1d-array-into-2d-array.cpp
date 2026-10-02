class Solution {
public:
    vector<vector<int>> construct2DArray(vector<int>& original, int n, int m) {

        vector<vector<int>> v(n, vector<int>(m));
        if (m * n != original.size()) {
            return {};
        }
        int k = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < m; j++) {
                v[i][j] = original[k];
                k++;
            }
        }
        return v;
    }
};