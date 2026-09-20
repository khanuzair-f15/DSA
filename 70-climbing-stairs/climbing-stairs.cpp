class Solution {
public:
    int climbStairs(int n) {

        //                      1
        // 1                    1
        // 1  11                2
        // 111 12 21            3
        // 1111 112 121 211 22  5
        // 111

        int ans = 0;

        vector<int> v = {0, 1};

        for (int i = 2; i <= n + 1; i++) {
            v.push_back(v[i - 1] + v[i - 2]);
        }
        return v[n+1];
    }
};