class Solution {
public:
    int reverseDegree(string s) {
        int sum = 0;
        // a = > 97
        // sum = sum + (97-96)*97-96+25;
        // sum += 1*26;
        int k = 1;
        for (auto i : s) {
            sum = sum + k * (26 - ((int(i) - 96)) + 1);
            k++;
            cout << ((int(i) - 96)) << " " << 26 - ((int(i) - 96)) + 1 << endl;
        }
        return sum;
    }
};