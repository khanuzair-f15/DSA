class Solution {
public:
    void setZeroes(vector<vector<int>>& matrix) {
        unordered_set<int> row;
        unordered_set<int> column;
        // loop chalaya or i or j ki vvalue nikali jin me bhi 0 present h
        for (int i = 0; i < matrix.size(); i++) {
            for (int j = 0; j < matrix[i].size(); j++) {
                if (matrix[i][j] == 0) {
                    row.insert(i);
                    column.insert(j);
                }
            }
        }
        // a mere pass i or j h inme se agar koi bhi rows ya column m or set me
        // to usse 0 kr do
        for (int i = 0; i < matrix.size(); i++) {
            for (int j = 0; j < matrix[i].size(); j++) {
                if (row.count(i) || column.count(j)) {
                    matrix[i][j] = 0;
                }
            }
        }
   
    }
};