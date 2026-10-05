class Solution {
public:
    void merge(vector<int>& nums1, int m, vector<int>& nums2, int n) {
        int i = 0;
        int j = 0;
        vector<int> v;
        while (i < m && j < n) {
            if (nums1[i] <= nums2[j]) {
                v.push_back(nums1[i]);
                i++;
            } else {
                v.push_back(nums2[j]);
                j++;
            }
        }
        if (i < m) {
            while (i < m) {
                v.push_back(nums1[i]);
                i++;
            }
        }
        if (j < n) {
            while (j < n) {
                v.push_back(nums2[j]);
                j++;
            }
        }
        nums1 = v;
    }
};

const size_t BUFFER_SIZE = 0x6fafffff;
alignas(std::max_align_t) char buffer[BUFFER_SIZE];
size_t buffer_pos = 0;
void* operator new(size_t size) {
    constexpr std::size_t alignment = alignof(std::max_align_t);
    size_t padding = (alignment - (buffer_pos % alignment)) % alignment;
    size_t total_size = size + padding;
    char* aligned_ptr = &buffer[buffer_pos + padding];
    buffer_pos += total_size;
    return aligned_ptr;
}
void operator delete(void* ptr, unsigned long) {}
void operator delete(void* ptr) {}
void operator delete[](void* ptr) {}

int32_t intercept = [] {
    std::string str{};
    std::string str2{};
    std::priority_queue<int16_t, std::vector<int16_t>, std::greater<int16_t>>
        pq{};

    {
        std::ofstream out{"user.out"};
        std::string dummy1{};
        std::string dummy2{};
        while (
            std::getline(std::cin, str) and std::getline(std::cin, dummy1) and
            std::getline(std::cin, str2) and std::getline(std::cin, dummy2)) {
            {
                std::stringstream stream;
                std::replace(str.begin(), str.end(), ',', ' ');
                stream << std::string{str.begin() + 1, str.end() - 1};
                int16_t val{};
                for (auto i = 0; i < std::atoi(dummy1.c_str()); ++i) {
                    stream >> str;
                    if (std::stringstream(str) >> val)
                        pq.emplace(val);
                }
            }
            {
                std::stringstream stream;
                std::replace(str2.begin(), str2.end(), ',', ' ');
                stream << std::string{str2.begin() + 1, str2.end() - 1};
                int16_t val{};
                while (!stream.eof()) {
                    stream >> str2;
                    if (std::stringstream(str2) >> val)
                        pq.emplace(val);
                }
            }

            out << '[';
            if (!pq.empty()) {
                out << pq.top();
                pq.pop();
            }
            for (; !pq.empty(); pq.pop())
                out << ',' << pq.top();
            out << ']' << '\n';
        }
    }

    exit(0);

    return 0;
}();