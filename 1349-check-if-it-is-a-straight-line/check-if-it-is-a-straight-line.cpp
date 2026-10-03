class Solution {
public:
    bool checkStraightLine(vector<vector<int>>& coordinates) {
        // if only 2 points return true
        if (coordinates[1][0] - coordinates[0][0] == 0) {
            for (int i = 1; i < coordinates.size(); i++) {
                if (coordinates[i][0] != coordinates[0][0]) {
                    return false; // Not a vertical line
                }
            }
            return true;
        }
        // find slope
        float m = (float)(coordinates[1][1] - coordinates[0][1]) /
                  (coordinates[1][0] - coordinates[0][0]);
        // eq of line is y = mx+b
        // finding b = y-m*x
        float b = (float)(coordinates[0][1] - m * coordinates[0][0]);

        for (int i = 1; i < coordinates.size(); i++) {
            if (coordinates[i][1] != m * coordinates[i][0] + b) {
                return false;
            }
        }

        return true;
    }
};