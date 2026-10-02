class Solution {
public:
    vector<vector<int>> construct2DArray(vector<int>& original, int n, int m) {

        if (m * n != original.size()) {
            return {};
        }

        vector<vector<int>> v(n, vector<int>(m));
        
        for (int i = 0; i < m * n; i++) {
            v[i / m][i % m] = original[i];
        }
        return v;
    }
};