class Solution {
public:
    int minimumOperations(vector<int>& nums) {
        int count = 0;
        for (int i = 0; i < nums.size(); i++) {
            int temp = nums.at(i) % 3;
            cout << temp << " ";
            if (temp == 1 || temp == 2)
                count += 1;
        }
        return count;
    }
};