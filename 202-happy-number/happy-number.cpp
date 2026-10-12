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
        while (true) {
            int y = sqsumdig(n);
            if (y == 1 || y == 7) {
                return true;
            } else if (y < 10) {
                return false;
            } else {
                n = y;
            }
        }
        return false;
    }
};