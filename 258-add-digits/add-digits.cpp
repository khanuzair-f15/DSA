class Solution {
public:
    int addDigits(int num) {

        // 38
        while (num >= 10) {
            int temp = num;
            int output = 0;
            while (temp != 0) {
                int digit = temp % 10;
                output = output + digit;
                temp = temp / 10;
            }
            num = output;
            output = 0;
        }

        return num;
    }
};