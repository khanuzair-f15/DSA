class Solution {
public:
    int maximumWealth(vector<vector<int>>& accounts) {
        int max = INT_MIN;
        int count = INT_MIN;

        for (int i = 0; i < accounts.size(); i++) {
            count = 0;
            for (int j = 0; j < accounts[i].size(); j++) {
                count += accounts[i][j];
                if (count > max) {
                    max = count;
                }
            }
        }
        return max;
    }
};