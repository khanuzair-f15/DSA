class Solution {
public:
    int mostFrequentEven(vector<int>& nums) {
     
        map<int, int> m;
        vector<int> v;
        for (auto i : nums) {
            if (i % 2 == 0) {
                m[i]++;
            }
        }
        int maxFreq = 0;
        int mostFrequent;

        for (auto i : m) {
            if (i.second > maxFreq) {
                maxFreq = i.second;
                v.push_back(i.first);
            }
        }
        if (v.empty()) {
            return -1;
        }
        sort(v.begin(), v.end(), greater<int>());
        return v[0];
    }
};