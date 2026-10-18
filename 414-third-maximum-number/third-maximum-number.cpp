class Solution {
public:
    int thirdMax(vector<int>& nums) {
        long long fm = LLONG_MIN;
        long long sm = LLONG_MIN;
        long long tm = LLONG_MIN;

        for (int i : nums) {
            // Skip duplicates
            if (i == fm || i == sm || i == tm) {
                continue;
            }

            if (i > fm) {
                tm = sm;
                sm = fm;
                fm = i;
            } 
            else if (i > sm) {
                tm = sm;
                sm = i;
            } 
            else if (i > tm) {
                tm = i;
            }
        }

        return tm == LLONG_MIN ? fm : tm;
    }
};