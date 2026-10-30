class Solution {
public:
    int rev(int r) {
        int rev = 0;

        while (r != 0) {
            int digit = r % 10;
            rev = rev * 10 + digit;
            r = r / 10;
        }
        return rev;
    }
    int sumOfPrimesInRange(int n) {
        int r = rev(n);
        int sum = 0;
        int flag = 0;
        int start = max(2, min(r, n));
        int end = max(r, n);
        for (int i = start; i <= end; i++) {
            for (int j = 2; j * j <= i; j++) {
                if (i % j == 0) {
                    flag = 1;
                    break;
                }
            }
            if (flag == 0) {
                cout << i << " ";
                sum = sum + i;
            }
            flag = 0;
        }
        return sum;
    }
};