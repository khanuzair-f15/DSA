class Solution {
public:
    int scoreOfString(string s) {

        int sum = 0;

        for (int i = 0; i < s.size() - 1; i++) {
            int x = (int)s[i] - (int)s[i + 1];
            if (x < 0) {
                x = x * -1;
            }
            sum = sum + x;
        }
        if (sum < 0) {
            sum = sum * -1;
        }
        return sum;
    }
};