class Solution {
public:
    vector<vector<int>> rotate(vector<vector<int>>& matrix) {
        int i = 0;
        int j = 0;
        for (i = 0; i < matrix.size(); i++) {
            for (j = i + 1; j < matrix.size(); j++) {
                swap(matrix[i][j], matrix[j][i]);
            }
        }
        i = 0;
        j = 0;
        for (i = 0; i < matrix.size(); i++) {
            for (j = 0; j < matrix.size() / 2; j++) {
                swap(matrix[i][j], matrix[i][matrix.size() - j - 1]);
            }
        }
        return matrix;
    };
    bool findRotation(vector<vector<int>>& mat, vector<vector<int>>& target) {
        for (int i = 0; i < 4; i++) {
            if (rotate(mat) == target) {
                return true;
            }
        }
        return false;
    }
};