class Solution {
public:
    int reverseDegree(string s) {
        int sum = 0;
        for (int i = 0; i < s.size(); i++) {
            sum = sum + (i + 1) * (26 - ((int(s[i]) - 96)) + 1);
        }
        return sum;
    }
};