class Solution {
public:
    int sqsumdig(int x) {
        long long sum = 0;
        while (x != 0) {
            int dig = x % 10;
            sum = sum + dig * dig;
            x = x / 10;
        }
        return sum;
    }
    bool isHappy(int n) {
        unordered_set<int> s;
        s.insert(n);
        while (true) {
            int y = sqsumdig(n);
            if (y == 1) {
                return true;
            } else if (s.find(y) != s.end()) {
                return false;
            } else {
                n = y;
                s.insert(n);
            }
        }

        // 19
        //
        return false;
    }
};